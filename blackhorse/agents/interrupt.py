"""
Phase 4B — Human Interruption Primitive.

A human must be able to cryptographically pause or override any agent
mid-operation. The interrupt command is as verifiable as the agent's
own attestation packets. Unsigned interrupts are rejected.

Lifecycle
---------
1. Human operator calls InterruptHandler.issue() → produces a signed
   InterruptCommand.
2. Agent polls for interrupt commands between every major operation.
3. Agent calls InterruptHandler.verify() → False means reject and ignore.
4. On a valid interrupt: agent halts, then calls generate_receipt() to
   prove it received and honored the command.

An agent that ignores a verified interrupt is in violation of its scope
attestation and can be flagged by ScopeValidator.flag_deviation().
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from ..crypto.signing.hmac_bhl import KEY_SIZE


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

InterruptCommandType = Literal["PAUSE", "STOP", "REDIRECT", "RESUME"]
VALID_COMMANDS: frozenset[str] = frozenset({"PAUSE", "STOP", "REDIRECT", "RESUME"})


# ---------------------------------------------------------------------------
# InterruptCommand
# ---------------------------------------------------------------------------

@dataclass
class InterruptCommand:
    """
    A signed interrupt command issued by a human operator.

    Attributes
    ----------
    command_id      : UUID uniquely identifying this interrupt.
    issuer_id       : Operator identifier (e.g. node_id or operator public key hash).
    target_agent_id : agent_id of the agent being interrupted.
    command         : One of PAUSE, STOP, REDIRECT, or RESUME.
    timestamp       : UTC datetime the command was issued.
    reason          : Human-readable reason, max 200 characters.
    signature       : HMAC-SHA256 over all above fields.
    """

    command_id: str
    issuer_id: str
    target_agent_id: str
    command: str
    timestamp: datetime
    reason: str
    signature: bytes = field(default=b"")

    def __post_init__(self) -> None:
        if self.command not in VALID_COMMANDS:
            raise ValueError(
                f"Invalid command: {self.command!r}. "
                f"Must be one of {sorted(VALID_COMMANDS)}"
            )

    def _canonical_bytes(self) -> bytes:
        """
        Deterministic serialisation of all fields except signature.

        Used as the HMAC input so that any field change invalidates the tag.
        """
        record = {
            "command_id": self.command_id,
            "issuer_id": self.issuer_id,
            "target_agent_id": self.target_agent_id,
            "command": self.command,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
        }
        return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "command_id": self.command_id,
            "issuer_id": self.issuer_id,
            "target_agent_id": self.target_agent_id,
            "command": self.command,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason,
            "signature": self.signature.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InterruptCommand":
        """Reconstruct from a plain dict (as produced by to_dict())."""
        return cls(
            command_id=data["command_id"],
            issuer_id=data["issuer_id"],
            target_agent_id=data["target_agent_id"],
            command=data["command"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reason=data["reason"],
            signature=bytes.fromhex(data["signature"]),
        )


# ---------------------------------------------------------------------------
# InterruptHandler
# ---------------------------------------------------------------------------

class InterruptHandler:
    """
    Issues, verifies, and acknowledges agent interrupt commands.

    Interrupts are the human override mechanism. Every interrupt must be
    signed by a human operator key. Agents verify the signature before
    honoring any interrupt. Receipt generation proves the agent received
    and honored the command — creating an auditable override trail.
    """

    def issue(
        self,
        target_agent_id: str,
        command: str,
        reason: str,
        issuer_id: str,
        signing_key: bytes,
    ) -> InterruptCommand:
        """
        Create and sign an interrupt command.

        Parameters
        ----------
        target_agent_id : agent_id of the agent to interrupt.
        command         : PAUSE, STOP, REDIRECT, or RESUME.
        reason          : Human-readable reason (truncated to 200 chars).
        issuer_id       : Operator identifier (any stable string).
        signing_key     : Human operator's 32-byte HMAC signing key.

        Returns
        -------
        InterruptCommand
            Signed interrupt command ready for transmission to the agent.
        """
        if len(reason) > 200:
            reason = reason[:197] + "..."

        cmd = InterruptCommand(
            command_id=str(uuid.uuid4()),
            issuer_id=issuer_id,
            target_agent_id=target_agent_id,
            command=command,
            timestamp=datetime.now(timezone.utc),
            reason=reason,
        )
        cmd.signature = _hmac.new(
            signing_key,
            cmd._canonical_bytes(),
            hashlib.sha256,
        ).digest()
        return cmd

    def verify(self, command: InterruptCommand, operator_public_key: bytes) -> bool:
        """
        Verify the HMAC signature on an interrupt command.

        Agents MUST call this before honoring any interrupt. Unsigned
        or tampered commands are rejected silently.

        Parameters
        ----------
        command             : The interrupt command to verify.
        operator_public_key : The operator's HMAC signing key used during issue().

        Returns
        -------
        bool
            True if signature is valid, False otherwise.
        """
        if not command.signature:
            return False
        expected = _hmac.new(
            operator_public_key,
            command._canonical_bytes(),
            hashlib.sha256,
        ).digest()
        return _hmac.compare_digest(expected, command.signature)

    def serialize(self, command: InterruptCommand) -> bytes:
        """
        Serialize an InterruptCommand to UTF-8 JSON bytes.

        For transmission through the Blackhorse pipeline, wrap the result
        in BlackhorseSession.pack() for encryption and signing.

        Parameters
        ----------
        command : The interrupt command to serialize.

        Returns
        -------
        bytes
            UTF-8 JSON bytes.
        """
        return json.dumps(command.to_dict(), separators=(",", ":")).encode("utf-8")

    @staticmethod
    def deserialize(data: bytes) -> InterruptCommand:
        """
        Deserialize an InterruptCommand from UTF-8 JSON bytes.

        Parameters
        ----------
        data : Bytes as produced by serialize().

        Returns
        -------
        InterruptCommand
        """
        return InterruptCommand.from_dict(json.loads(data.decode("utf-8")))

    def generate_receipt(
        self,
        command: InterruptCommand,
        agent_signing_key: bytes,
    ) -> bytes:
        """
        Generate a signed receipt proving the agent received and honored the interrupt.

        The receipt is HMAC-signed by the agent's key, proving the specific
        agent (identified by agent_id = SHA-256 of its signing key) received
        and honored the command.

        Parameters
        ----------
        command           : The interrupt command being acknowledged.
        agent_signing_key : The receiving agent's 32-byte HMAC signing key.

        Returns
        -------
        bytes
            UTF-8 JSON receipt bytes signed by the agent's key.
        """
        agent_id = hashlib.sha256(agent_signing_key).hexdigest()
        receipt_body: dict = {
            "command_id": command.command_id,
            "agent_id": agent_id,
            "target_agent_id": command.target_agent_id,
            "command": command.command,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
            "status": "HONORED",
        }
        canonical = json.dumps(
            receipt_body, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        tag = _hmac.new(agent_signing_key, canonical, hashlib.sha256).digest()
        receipt_body["signature"] = tag.hex()
        return json.dumps(receipt_body, separators=(",", ":")).encode("utf-8")
