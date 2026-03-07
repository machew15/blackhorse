"""
Phase 4A — Agent Decision Attestation.

Every autonomous decision made by a Blackhorse agent must be attested
before execution. The AttestationPacket IS the permission to execute —
no agent output is acted upon without a valid, verifiable packet.

Wire model
----------
An AgentDecisionPacket binds together:
  - WHO decided       (agent_id = SHA-256 of signing key)
  - WHAT was decided  (input_hash, output_hash)
  - WHY               (reasoning_summary)
  - WHEN              (timestamp)
  - UNDER WHAT SCOPE  (scope_ref)

The whole record is signed with HMAC-SHA256 so that tampering with any
field invalidates the signature.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..crypto.signing.hmac_bhl import KEY_SIZE


# ---------------------------------------------------------------------------
# AgentDecisionPacket
# ---------------------------------------------------------------------------

@dataclass
class AgentDecisionPacket:
    """
    A signed attestation record for a single agent decision.

    Attributes
    ----------
    agent_id          : SHA-256 of agent signing key (hex string).
    decision_id       : UUID uniquely identifying this decision.
    timestamp         : UTC datetime when the decision was made.
    input_hash        : SHA-256 of the raw input bytes (hex string).
    reasoning_summary : Human-readable summary, max 500 characters.
    output_hash       : SHA-256 of the output bytes (hex string).
    scope_ref         : Scope ID the decision was made under.
    signature         : HMAC-SHA256 over all above fields (set by DecisionAttestor).
    """

    agent_id: str
    decision_id: str
    timestamp: datetime
    input_hash: str
    reasoning_summary: str
    output_hash: str
    scope_ref: str
    signature: bytes = field(default=b"")

    def _canonical_bytes(self) -> bytes:
        """
        Deterministic serialisation of all fields except signature.

        Used as the HMAC input — any change to any field changes the digest.
        """
        record = {
            "agent_id": self.agent_id,
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "input_hash": self.input_hash,
            "reasoning_summary": self.reasoning_summary,
            "output_hash": self.output_hash,
            "scope_ref": self.scope_ref,
        }
        return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "agent_id": self.agent_id,
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "input_hash": self.input_hash,
            "reasoning_summary": self.reasoning_summary,
            "output_hash": self.output_hash,
            "scope_ref": self.scope_ref,
            "signature": self.signature.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentDecisionPacket":
        """Reconstruct from a plain dict (as produced by to_dict())."""
        return cls(
            agent_id=data["agent_id"],
            decision_id=data["decision_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            input_hash=data["input_hash"],
            reasoning_summary=data["reasoning_summary"],
            output_hash=data["output_hash"],
            scope_ref=data["scope_ref"],
            signature=bytes.fromhex(data["signature"]),
        )


# ---------------------------------------------------------------------------
# DecisionAttestor
# ---------------------------------------------------------------------------

class DecisionAttestor:
    """
    Creates and verifies AgentDecisionPacket records.

    Every call to ``attest()`` produces a signed packet that must be
    verified before the corresponding output is acted upon. This creates
    an unforgeable, auditable trail of every decision the agent makes.

    Parameters
    ----------
    signing_key : 32-byte HMAC key that identifies this agent.
                  The agent_id is derived as SHA-256 of this key.
    """

    def __init__(self, signing_key: bytes) -> None:
        if len(signing_key) != KEY_SIZE:
            raise ValueError(
                f"signing_key must be {KEY_SIZE} bytes, got {len(signing_key)}"
            )
        self._signing_key = signing_key
        self._agent_id = hashlib.sha256(signing_key).hexdigest()

    @property
    def agent_id(self) -> str:
        """SHA-256 of this agent's signing key (hex)."""
        return self._agent_id

    def attest(
        self,
        input_bytes: bytes,
        reasoning: str,
        output_bytes: bytes,
        scope_ref: str,
    ) -> AgentDecisionPacket:
        """
        Create and sign an AgentDecisionPacket before output is acted upon.

        This method must be called before executing any agent output. The
        returned packet is the proof that the decision was deliberate, within
        scope, and cryptographically committed to.

        Parameters
        ----------
        input_bytes  : Raw bytes of the input that triggered this decision.
        reasoning    : Human-readable explanation, max 500 characters.
        output_bytes : Raw bytes of the output that will be acted upon.
        scope_ref    : ID of the AgentScope governing this agent.

        Returns
        -------
        AgentDecisionPacket
            Signed attestation. Verify before executing the output.
        """
        if len(reasoning) > 500:
            reasoning = reasoning[:497] + "..."

        packet = AgentDecisionPacket(
            agent_id=self._agent_id,
            decision_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc),
            input_hash=hashlib.sha256(input_bytes).hexdigest(),
            reasoning_summary=reasoning,
            output_hash=hashlib.sha256(output_bytes).hexdigest(),
            scope_ref=scope_ref,
        )
        packet.signature = _hmac.new(
            self._signing_key,
            packet._canonical_bytes(),
            hashlib.sha256,
        ).digest()
        return packet

    def verify(self, packet: AgentDecisionPacket, signing_key: bytes) -> bool:
        """
        Verify the HMAC signature on an AgentDecisionPacket.

        Parameters
        ----------
        packet      : The packet to verify.
        signing_key : The signing key of the agent that produced this packet.

        Returns
        -------
        bool
            True if signature is valid, False if tampered or key mismatch.
        """
        if not packet.signature:
            return False
        expected = _hmac.new(
            signing_key,
            packet._canonical_bytes(),
            hashlib.sha256,
        ).digest()
        return _hmac.compare_digest(expected, packet.signature)

    def serialize(self, packet: AgentDecisionPacket) -> bytes:
        """
        Serialize an AgentDecisionPacket to UTF-8 JSON bytes.

        For on-wire transmission, wrap the result in
        ``BlackhorseSession.pack()`` to ensure encryption and signing.

        Parameters
        ----------
        packet : The packet to serialize.

        Returns
        -------
        bytes
            UTF-8 JSON representation of the packet.
        """
        return json.dumps(packet.to_dict(), separators=(",", ":")).encode("utf-8")

    @staticmethod
    def deserialize(data: bytes) -> AgentDecisionPacket:
        """
        Deserialize an AgentDecisionPacket from UTF-8 JSON bytes.

        Parameters
        ----------
        data : Bytes as produced by serialize().

        Returns
        -------
        AgentDecisionPacket
        """
        return AgentDecisionPacket.from_dict(json.loads(data.decode("utf-8")))

    @staticmethod
    def generate_key() -> bytes:
        """Generate a cryptographically secure 256-bit signing key."""
        return os.urandom(KEY_SIZE)
