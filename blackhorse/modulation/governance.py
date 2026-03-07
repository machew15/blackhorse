"""
SIMULATION ONLY — Parametric governance constraints for modulation research.

ModulationPolicy enforces constraints that are baked into the signal model
itself rather than applied as external policy after the fact. All validation
is pure Python — no RF, no spectrum, no hardware.

Education mode is on by default: every output carries a plain-English
explanation of what the numbers mean and why constraints exist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional, Tuple

from blackhorse.compression import compress
from blackhorse.crypto.signing import BHLSigner
from blackhorse.modulation.analyzer import EfficiencyReport
from blackhorse.modulation.symbols import ModulationScheme

if TYPE_CHECKING:
    from blackhorse.modulation.media import (
        MediaAttestation,
        MediaAttestor,
        MediaConstraints,
        MediaType,
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PolicyViolationError(Exception):
    """Raised when a payload fails ModulationPolicy validation."""


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


@dataclass
class ModulationConstraints:
    """Parametric constraints on simulated modulation use.

    These are governance parameters embedded in the simulation model itself.
    Constraints are checked before any output is produced. Nothing is
    transmitted — all enforcement is mathematical and local.
    """

    max_symbol_rate: int = 1_000_000
    """Maximum simulated symbols per second (not a real hardware limit)."""

    max_payload_bytes: int = 65_536
    """Maximum payload size accepted by this policy."""

    min_compression_ratio: float = 1.0
    """Minimum required compression ratio. 1.0 means no constraint.
    Set > 1.0 to require that compression actually reduces byte count."""

    allowed_schemes: List[str] = field(
        default_factory=lambda: ["BPSK", "QPSK", "QAM16", "QAM64"]
    )
    """Modulation scheme names permitted by this policy."""

    require_attestation: bool = True
    """When True, all outputs must carry a signed attestation packet."""

    education_mode: bool = True
    """When True, every GovernedOutput carries a plain-English explanation."""


# ---------------------------------------------------------------------------
# DecisionAttestor
# ---------------------------------------------------------------------------


class DecisionAttestor:
    """Signs governance decision outputs for verifiable attestation.

    Uses HMAC-SHA256 (via BHLSigner) to produce a signed packet that
    embeds the efficiency report summary and the policy decision. The
    resulting bytes can be stored or verified later without re-running
    the simulation.

    SIMULATION ONLY — signatures are for data integrity, not spectrum licensing.
    """

    def __init__(self, node_id: str, signing_key: bytes) -> None:
        self._node_id = node_id
        self._signing_key = signing_key

    def attest(self, report: EfficiencyReport, decision: str) -> bytes:
        """Produce a signed attestation packet for a governance decision.

        *decision* is a short string such as ``"APPROVED"`` or the
        rejection reason string from ``validate()``.

        Returns the signed packet bytes produced by BHLSigner.
        """
        payload = json.dumps(
            {
                "node_id": self._node_id,
                "decision": decision,
                "scheme": report.scheme,
                "input_bytes": report.input_bytes,
                "compressed_bytes": report.compressed_bytes,
                "compression_ratio": report.compression_ratio,
                "symbol_reduction_pct": report.symbol_reduction_pct,
                "energy_savings_pct": report.energy_savings_pct,
                "timestamp": report.timestamp.isoformat(),
            },
            separators=(",", ":"),
        ).encode()
        return BHLSigner().sign(payload, self._signing_key)

    @staticmethod
    def generate_key() -> bytes:
        """Generate a fresh 32-byte signing key."""
        return BHLSigner.generate_key()

    @staticmethod
    def verify(signed_bytes: bytes, key: bytes) -> bool:
        """Return True if *signed_bytes* has a valid signature under *key*."""
        return BHLSigner().verify(signed_bytes, key)


# ---------------------------------------------------------------------------
# GovernedOutput
# ---------------------------------------------------------------------------


@dataclass
class GovernedOutput:
    """A policy-governed simulation output.

    Carries the efficiency report, policy verdict, optional attestation
    packet, and a plain-English education note. Extended fields support
    media provenance when a MediaAttestor is configured.

    SIMULATION ONLY — not a transmission record.
    """

    report: EfficiencyReport
    policy_approved: bool
    attestation_packet: Optional[bytes] = None
    education_note: Optional[str] = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Media provenance extension (populated when media_attestor is configured)
    media_attestation: Optional["MediaAttestation"] = None
    provenance_chain: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ModulationPolicy
# ---------------------------------------------------------------------------


class ModulationPolicy:
    """Enforces parametric governance constraints on the modulation simulation.

    Constraints are checked in a fixed order before any output is produced.
    Rejected payloads raise ``PolicyViolationError`` from ``apply()``.
    All approved outputs may carry a signed attestation and an education note.

    SIMULATION ONLY — no spectrum, no hardware, no RF.
    """

    def __init__(
        self,
        constraints: ModulationConstraints,
        attestor: Optional[DecisionAttestor] = None,
        media_constraints: Optional["MediaConstraints"] = None,
        media_attestor: Optional["MediaAttestor"] = None,
    ) -> None:
        self._constraints = constraints
        self._attestor = attestor
        self._media_constraints = media_constraints
        self._media_attestor = media_attestor

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(
        self, data: bytes, scheme: ModulationScheme
    ) -> Tuple[bool, str]:
        """Check policy constraints for *data* under *scheme*.

        Check order:
          1. ``len(data) <= max_payload_bytes``
          2. ``scheme.name in allowed_schemes``
          3. If ``min_compression_ratio > 1.0``: verify compression reduces size.

        Returns ``(True, "APPROVED")`` or ``(False, <reason>)``.
        """
        c = self._constraints

        if len(data) > c.max_payload_bytes:
            return (
                False,
                f"PAYLOAD_TOO_LARGE: {len(data)} bytes exceeds "
                f"max_payload_bytes={c.max_payload_bytes}",
            )

        if scheme.name not in c.allowed_schemes:
            return (
                False,
                f"SCHEME_NOT_ALLOWED: {scheme.name} not in "
                f"allowed_schemes={c.allowed_schemes}",
            )

        if c.min_compression_ratio > 1.0:
            compressed_len = len(compress(data))
            ratio = len(data) / compressed_len if compressed_len else 0.0
            if ratio < c.min_compression_ratio:
                return (
                    False,
                    f"COMPRESSION_BELOW_MINIMUM: achieved ratio={ratio:.4f} "
                    f"< required min_compression_ratio={c.min_compression_ratio}",
                )

        return (True, "APPROVED")

    def validate_media(
        self,
        data: bytes,
        filename: str,
        media_type: "MediaType",
    ) -> Tuple[bool, str]:
        """Check media-specific policy constraints.

        If no ``media_constraints`` were configured, returns
        ``(True, "NO_MEDIA_POLICY")``.

        Check order:
          1. ``media_type.value in allowed_media_types``
          2. ``len(data) <= size limit for this media_type``
          3. VIDEO always requires human approval — automatic rejection.

        Returns ``(True, "APPROVED")`` or ``(False, <reason>)``.
        """
        if self._media_constraints is None:
            return (True, "NO_MEDIA_POLICY")

        # Import deferred to avoid circular import at module load time.
        from blackhorse.modulation.media import MediaType  # noqa: PLC0415

        mc = self._media_constraints

        # VIDEO always requires explicit human sign-off — checked first so that
        # "VIDEO_REQUIRES_HUMAN_APPROVAL" is always the returned reason, even
        # when video is absent from allowed_media_types.
        if media_type == MediaType.VIDEO:
            return (False, "VIDEO_REQUIRES_HUMAN_APPROVAL")

        if media_type.value not in mc.allowed_media_types:
            return (
                False,
                f"MEDIA_TYPE_NOT_ALLOWED: {media_type.value} not in "
                f"allowed_media_types={mc.allowed_media_types}",
            )

        # Per-type size limits.
        size_limits = {
            MediaType.IMAGE:    mc.max_image_bytes,
            MediaType.AUDIO:    mc.max_audio_bytes,
            MediaType.DOCUMENT: mc.max_document_bytes,
            MediaType.TEXT:     mc.max_payload_bytes,
            MediaType.UNKNOWN:  mc.max_payload_bytes,
        }
        limit = size_limits.get(media_type, mc.max_payload_bytes)
        if len(data) > limit:
            return (
                False,
                f"MEDIA_TOO_LARGE: {len(data)} bytes exceeds limit "
                f"of {limit} for {media_type.value}",
            )

        return (True, "APPROVED")

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------

    def apply(
        self,
        data: bytes,
        scheme: ModulationScheme,
        report: EfficiencyReport,
    ) -> GovernedOutput:
        """Apply governance constraints and produce a GovernedOutput.

        Steps:
          1. Call ``validate()`` — raises PolicyViolationError if rejected.
          2. Optionally produce a signed attestation packet.
          3. Optionally attach an education note.

        Raises ``PolicyViolationError`` if validation fails.
        Returns a ``GovernedOutput`` on approval.
        """
        approved, reason = self.validate(data, scheme)
        if not approved:
            raise PolicyViolationError(reason)

        attestation_packet: Optional[bytes] = None
        if self._constraints.require_attestation and self._attestor:
            attestation_packet = self._attestor.attest(report, reason)

        education_note: Optional[str] = None
        if self._constraints.education_mode:
            education_note = self._build_education_note(report, reason)

        return GovernedOutput(
            report=report,
            policy_approved=True,
            attestation_packet=attestation_packet,
            education_note=education_note,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_education_note(
        self, report: EfficiencyReport, decision: str
    ) -> str:
        """Build a plain-English explanation of the simulation result."""
        lines = [
            "── SIMULATION EDUCATION NOTE " + "─" * 50,
            "",
            "COMPRESSION RATIO:",
            f"  {report.compression_ratio:.4f}× means the BHL engine compressed",
            f"  {report.input_bytes} bytes down to {report.compressed_bytes} bytes.",
            "  A ratio > 1.0 means the data got smaller. A ratio < 1.0 means",
            "  compression actually made it larger (overhead exceeded savings).",
            "",
            "SYMBOL REDUCTION:",
            f"  Fewer symbols = less simulated energy. Sending compressed data",
            f"  required {report.symbols_compressed} symbols vs",
            f"  {report.symbols_uncompressed} for raw data under {report.scheme}.",
            f"  That is a {report.symbol_reduction_pct:.1f}% reduction.",
            "",
            "ENERGY SAVINGS:",
            f"  Simulated energy cost dropped by {report.energy_savings_pct:.1f}%.",
            "  In a real low-bandwidth system, this translates to longer battery",
            "  life, lower cost-per-bit, or more capacity on a congested channel.",
            "  These numbers are SIMULATION UNITS — not real watts.",
            "",
            "GOVERNANCE DECISION:",
            f"  {decision}",
            "  Parametric governance means the constraints are baked into the",
            "  model itself. A rejected payload is never processed further.",
            "",
            "WHO USES THIS DATA:",
            "  Researchers studying compression efficiency in low-bandwidth",
            "  environments — satellite, mesh radio, rural IoT, emergency comms.",
            "  The signed attestation packet allows third-party verification",
            "  of the simulation result without re-running the simulation.",
            "─" * 79,
        ]
        return "\n".join(lines)
