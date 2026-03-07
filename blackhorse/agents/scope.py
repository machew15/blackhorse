"""
Phase 4C — Agent Scope Attestation.

Every Blackhorse agent carries a signed constitution (AgentScope) defining
exactly what it may and may not do. The scope is signed by a human operator
at agent birth and is immutable afterward — any change requires a new
scope_id and operator re-signing.

Lifecycle
---------
1. Operator calls ScopeValidator.create_scope() → unsigned AgentScope.
2. Operator calls ScopeValidator.sign_scope() → signed AgentScope.
3. At runtime, agent calls ScopeValidator.validate() before each action.
4. If the action is out-of-scope, ScopeValidator.flag_deviation() produces
   a signed DeviationReport for the ledger and the operator.

Design rule: prohibited_actions always win over permitted_actions.
Actions not appearing in either list are denied by default.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..crypto.signing.hmac_bhl import KEY_SIZE


# ---------------------------------------------------------------------------
# AgentScope
# ---------------------------------------------------------------------------

@dataclass
class AgentScope:
    """
    A signed constitution defining what an agent may and may not do.

    Attributes
    ----------
    scope_id             : UUID generated at agent initialization.
    agent_id             : SHA-256 of agent signing key (hex).
    created_at           : UTC datetime; immutable after signing.
    version              : Semver string, e.g. "1.0.0".
    permitted_actions    : Explicit allowlist of permitted action strings.
    prohibited_actions   : Explicit denylist of prohibited action strings.
    max_autonomy_seconds : Maximum runtime seconds without a human check-in.
    data_access_scope    : Data sources the agent may read.
    output_destinations  : Destinations the agent may write/post/transmit to.
    signature            : HMAC-SHA256 signed by the human operator at creation.
    """

    scope_id: str
    agent_id: str
    created_at: datetime
    version: str
    permitted_actions: list[str]
    prohibited_actions: list[str]
    max_autonomy_seconds: int
    data_access_scope: list[str]
    output_destinations: list[str]
    signature: bytes = field(default=b"")

    def _canonical_bytes(self) -> bytes:
        """
        Deterministic serialisation of all fields except signature.

        Lists are sorted before serialisation so field order never affects
        the digest.
        """
        record = {
            "scope_id": self.scope_id,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "permitted_actions": sorted(self.permitted_actions),
            "prohibited_actions": sorted(self.prohibited_actions),
            "max_autonomy_seconds": self.max_autonomy_seconds,
            "data_access_scope": sorted(self.data_access_scope),
            "output_destinations": sorted(self.output_destinations),
        }
        return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "scope_id": self.scope_id,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "permitted_actions": self.permitted_actions,
            "prohibited_actions": self.prohibited_actions,
            "max_autonomy_seconds": self.max_autonomy_seconds,
            "data_access_scope": self.data_access_scope,
            "output_destinations": self.output_destinations,
            "signature": self.signature.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentScope":
        """Reconstruct from a plain dict (as produced by to_dict())."""
        return cls(
            scope_id=data["scope_id"],
            agent_id=data["agent_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            version=data["version"],
            permitted_actions=data["permitted_actions"],
            prohibited_actions=data["prohibited_actions"],
            max_autonomy_seconds=data["max_autonomy_seconds"],
            data_access_scope=data["data_access_scope"],
            output_destinations=data["output_destinations"],
            signature=bytes.fromhex(data["signature"]),
        )


# ---------------------------------------------------------------------------
# DeviationReport
# ---------------------------------------------------------------------------

@dataclass
class DeviationReport:
    """
    A signed record of an agent attempting an out-of-scope action.

    Produced by ScopeValidator.flag_deviation(). Stored in the ledger
    and transmitted to the operator.

    Attributes
    ----------
    report_id   : UUID for this report.
    decision_id : ID of the AgentDecisionPacket that triggered the deviation.
    scope_id    : The scope that was violated.
    agent_id    : The agent that attempted the action.
    action      : The action string that was attempted.
    violation   : Human-readable description of the violation.
    timestamp   : UTC datetime the deviation occurred.
    signature   : HMAC-SHA256 signed by the agent's key.
    """

    report_id: str
    decision_id: str
    scope_id: str
    agent_id: str
    action: str
    violation: str
    timestamp: datetime
    signature: bytes = field(default=b"")

    def to_dict(self) -> dict:
        """Serialise to a plain dict (JSON-safe)."""
        return {
            "report_id": self.report_id,
            "decision_id": self.decision_id,
            "scope_id": self.scope_id,
            "agent_id": self.agent_id,
            "action": self.action,
            "violation": self.violation,
            "timestamp": self.timestamp.isoformat(),
            "signature": self.signature.hex(),
        }


# ---------------------------------------------------------------------------
# ScopeValidator
# ---------------------------------------------------------------------------

class ScopeValidator:
    """
    Validates agent actions against a signed AgentScope and flags deviations.

    Design rule: a prohibited_action always beats a permitted_action.
    An action not in either list is denied by default.
    """

    def validate(
        self,
        action: str,
        scope: AgentScope,
        signing_key: bytes,
    ) -> tuple[bool, str]:
        """
        Check whether an action is permitted under the given scope.

        Parameters
        ----------
        action      : The action string to validate.
        scope       : The signed AgentScope to check against.
        signing_key : Agent's signing key used to verify the scope signature.

        Returns
        -------
        tuple[bool, str]
            (True, "APPROVED") if the action is permitted.
            (False, reason)    if the action is denied or scope is invalid.
        """
        if not self._verify_scope_signature(scope, signing_key):
            return False, (
                "SCOPE_SIGNATURE_INVALID: scope may have been tampered with "
                f"(scope_id={scope.scope_id})"
            )

        if action in scope.prohibited_actions:
            return False, (
                f"PROHIBITED: action '{action}' is explicitly prohibited "
                f"by scope {scope.scope_id}"
            )

        if action not in scope.permitted_actions:
            return False, (
                f"NOT_PERMITTED: action '{action}' is not in permitted_actions "
                f"for scope {scope.scope_id}"
            )

        return True, "APPROVED"

    def flag_deviation(
        self,
        action: str,
        scope: AgentScope,
        decision_id: str,
        agent_signing_key: bytes,
    ) -> bytes:
        """
        Create a signed DeviationReport when an agent attempts an out-of-scope action.

        The report is signed by the agent's key and should be stored in the
        ledger and transmitted to the human operator.

        Parameters
        ----------
        action            : The action that was attempted.
        scope             : The AgentScope that was violated.
        decision_id       : ID of the AgentDecisionPacket that triggered the deviation.
        agent_signing_key : Agent's 32-byte HMAC signing key.

        Returns
        -------
        bytes
            UTF-8 JSON bytes of the signed DeviationReport.
        """
        agent_id = hashlib.sha256(agent_signing_key).hexdigest()
        report = DeviationReport(
            report_id=str(uuid.uuid4()),
            decision_id=decision_id,
            scope_id=scope.scope_id,
            agent_id=agent_id,
            action=action,
            violation=(
                f"Agent attempted action '{action}' which is not permitted "
                f"under scope {scope.scope_id} (version {scope.version})"
            ),
            timestamp=datetime.now(timezone.utc),
        )
        body = {k: v for k, v in report.to_dict().items() if k != "signature"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        tag = _hmac.new(agent_signing_key, canonical, hashlib.sha256).digest()
        report.signature = tag
        return json.dumps(report.to_dict(), separators=(",", ":")).encode("utf-8")

    def sign_scope(self, scope: AgentScope, operator_signing_key: bytes) -> AgentScope:
        """
        Sign an AgentScope with the operator's key.

        Must be called once at agent birth. The scope is immutable after signing.
        Any scope change requires a new scope_id and operator re-signing.

        Parameters
        ----------
        scope                : The AgentScope to sign (must have an empty signature).
        operator_signing_key : Human operator's 32-byte HMAC signing key.

        Returns
        -------
        AgentScope
            The same scope object with the signature field populated.
        """
        scope.signature = _hmac.new(
            operator_signing_key,
            scope._canonical_bytes(),
            hashlib.sha256,
        ).digest()
        return scope

    @staticmethod
    def create_scope(
        agent_id: str,
        version: str,
        permitted_actions: list[str],
        prohibited_actions: list[str],
        max_autonomy_seconds: int,
        data_access_scope: list[str],
        output_destinations: list[str],
    ) -> AgentScope:
        """
        Create a new unsigned AgentScope.

        Call ``sign_scope()`` after creation to make it active.

        Parameters
        ----------
        agent_id             : SHA-256 of agent signing key (hex).
        version              : Semver string, e.g. "1.0.0".
        permitted_actions    : Explicit allowlist of action strings.
        prohibited_actions   : Explicit denylist of action strings.
        max_autonomy_seconds : Max seconds of autonomous operation.
        data_access_scope    : Data sources the agent may read.
        output_destinations  : Destinations the agent may write to.

        Returns
        -------
        AgentScope
            Unsigned scope. Must be signed by the operator before use.
        """
        return AgentScope(
            scope_id=str(uuid.uuid4()),
            agent_id=agent_id,
            created_at=datetime.now(timezone.utc),
            version=version,
            permitted_actions=list(permitted_actions),
            prohibited_actions=list(prohibited_actions),
            max_autonomy_seconds=max_autonomy_seconds,
            data_access_scope=list(data_access_scope),
            output_destinations=list(output_destinations),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_scope_signature(scope: AgentScope, key: bytes) -> bool:
        """Verify the HMAC signature on an AgentScope."""
        if not scope.signature:
            return False
        expected = _hmac.new(key, scope._canonical_bytes(), hashlib.sha256).digest()
        return _hmac.compare_digest(expected, scope.signature)
