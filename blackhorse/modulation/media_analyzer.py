"""
SIMULATION ONLY — Media-aware efficiency analysis with provenance tracking.

Extends EfficiencyAnalyzer to handle content-type-specific governance,
attestation, and human-readable provenance notes for each analyzed file.

No media is transmitted. Files are read locally, hashed, and analyzed.
Nothing leaves the machine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from blackhorse.modulation.analyzer import EfficiencyAnalyzer, EfficiencyReport
from blackhorse.modulation.media import (
    MediaAttestor,
    MediaConstraints,
    MediaType,
)
from blackhorse.modulation.symbols import ModulationScheme


# ---------------------------------------------------------------------------
# MediaEfficiencyReport
# ---------------------------------------------------------------------------


@dataclass
class MediaEfficiencyReport(EfficiencyReport):
    """Extends EfficiencyReport with media provenance and governance fields.

    Inherits all efficiency metrics from EfficiencyReport. The additional
    fields carry content-type identity, provenance hashes, human-approval
    status, and a plain-English governance note.

    All energy values remain SIMULATION UNITS — not real watts.
    """

    media_type: str = ""
    filename: str = ""
    content_hash: str = ""
    human_approved: bool = False
    provenance_verified: bool = False
    governance_note: str = ""


# ---------------------------------------------------------------------------
# MediaEfficiencyAnalyzer
# ---------------------------------------------------------------------------


class MediaEfficiencyAnalyzer(EfficiencyAnalyzer):
    """Extends EfficiencyAnalyzer for content-type-aware media analysis.

    Combines BHL compression efficiency measurement with MediaAttestor
    provenance and MediaConstraints governance checks. Every report carries
    a governance_note explaining in plain English what happened and why.

    SIMULATION ONLY — no spectrum, no transmission, no hardware.
    """

    def __init__(
        self,
        scheme: ModulationScheme,
        constraints: MediaConstraints,
        attestor: MediaAttestor,
    ) -> None:
        super().__init__(scheme)
        self._constraints = constraints
        self._attestor = attestor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_file(self, filepath: str) -> MediaEfficiencyReport:
        """Read *filepath* locally and produce a MediaEfficiencyReport.

        Steps:
          1. Read file bytes.
          2. Produce a MediaAttestation (detect type, hash, compress, sign).
          3. Check MediaConstraints for this content type.
          4. Run base EfficiencyAnalyzer.analyze() on raw bytes.
          5. Build MediaEfficiencyReport with provenance fields.

        Does NOT transmit the file. Local analysis only.
        """
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as fh:
            data = fh.read()
        return self.analyze_bytes(data, filename)

    def analyze_bytes(
        self, data: bytes, filename: str
    ) -> MediaEfficiencyReport:
        """Analyze *data* (as if it were a file named *filename*).

        Identical to ``analyze_file`` but accepts bytes directly.
        Use for simulation with synthetically generated test data.
        No real file I/O required.
        """
        # --- Attestation ------------------------------------------------
        signing_key = self._attestor._signing_key  # type: ignore[attr-defined]
        attestation = self._attestor.attest(data, filename, signing_key)

        # --- Governance check -------------------------------------------
        mc = self._constraints
        mt = attestation.media_type
        approved, gov_reason = self._check_constraints(data, mt)

        # --- Base efficiency analysis -----------------------------------
        base: EfficiencyReport = super().analyze(data)

        # --- Provenance verification ------------------------------------
        provenance_ok = self._attestor.verify(attestation, data, signing_key)

        # --- Build report -----------------------------------------------
        return MediaEfficiencyReport(
            # Inherited fields from EfficiencyReport.
            input_bytes=base.input_bytes,
            compressed_bytes=base.compressed_bytes,
            compression_ratio=base.compression_ratio,
            scheme=base.scheme,
            symbols_uncompressed=base.symbols_uncompressed,
            symbols_compressed=base.symbols_compressed,
            symbol_reduction_pct=base.symbol_reduction_pct,
            energy_uncompressed=base.energy_uncompressed,
            energy_compressed=base.energy_compressed,
            energy_savings_pct=base.energy_savings_pct,
            timestamp=base.timestamp,
            # Media-specific fields.
            media_type=mt.value,
            filename=filename,
            content_hash=attestation.content_hash,
            human_approved=attestation.human_approved,
            provenance_verified=provenance_ok,
            governance_note=self._build_governance_note(
                attestation=attestation,
                approved=approved,
                reason=gov_reason,
                base=base,
            ),
        )

    def simulate_media_corpus(self) -> List[MediaEfficiencyReport]:
        """Generate synthetic test data for each MediaType and analyze it.

        Produces one report per content type using locally generated bytes.
        No real files are required — pure simulation.

        Returns:
          A list of MediaEfficiencyReport, one per synthesized content type.
        """
        from blackhorse.modulation.samples import (  # noqa: PLC0415
            SAMPLE_INSTITUTIONAL_TEXT,
        )

        # Keep payloads small — BHL LZ77 compression is O(n²) on the window.
        # Sizes here are chosen to demonstrate each media type while keeping
        # total simulation time well under 1 second.
        corpus: list[tuple[bytes, str]] = [
            # TEXT — real institutional text content (~400 bytes).
            (
                SAMPLE_INSTITUTIONAL_TEXT[0].encode("utf-8"),
                "sample_institutional.txt",
            ),
            # IMAGE — 512 bytes with PNG magic header.
            (
                b"\x89PNG\r\n\x1a\n" + _pseudo_random_bytes(504, seed=1),
                "synthetic_image.png",
            ),
            # AUDIO — 512 bytes with MP3 magic header.
            (
                b"ID3" + _pseudo_random_bytes(509, seed=2),
                "synthetic_audio.mp3",
            ),
            # VIDEO — 512 bytes with MP4 ftyp magic (blocked by policy).
            (
                b"\x00\x00\x00\x18ftyp" + _pseudo_random_bytes(506, seed=3),
                "synthetic_video.mp4",
            ),
            # DOCUMENT — PDF-style text (~512 bytes).
            (
                b"%PDF-1.7\n" + (b"BT /F1 12 Tf (Simulation data.) Tj ET\n" * 13),
                "synthetic_document.pdf",
            ),
        ]

        reports: list[MediaEfficiencyReport] = []
        for data, filename in corpus:
            reports.append(self.analyze_bytes(data, filename))
        return reports

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_constraints(
        self, data: bytes, media_type: MediaType
    ) -> tuple[bool, str]:
        """Check MediaConstraints for *data* of *media_type*.

        Returns (approved: bool, reason: str).
        """
        mc = self._constraints

        if media_type == MediaType.VIDEO:
            return (False, "VIDEO_REQUIRES_HUMAN_APPROVAL")

        if media_type.value not in mc.allowed_media_types:
            return (False, f"MEDIA_TYPE_NOT_ALLOWED: {media_type.value}")

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
                f"MEDIA_TOO_LARGE: {len(data)} bytes > limit {limit}",
            )

        return (True, "APPROVED")

    @staticmethod
    def _build_governance_note(
        *,
        attestation: object,
        approved: bool,
        reason: str,
        base: EfficiencyReport,
    ) -> str:
        """Build a plain-English governance note for the report."""
        att = attestation  # type: ignore[assignment]
        lines = [
            f"Content type  : {att.media_type.value.upper()}",
            f"Filename      : {att.filename}",
            f"Governance    : {'APPROVED' if approved else 'BLOCKED — ' + reason}",
            f"Human approval: {'required (video)' if not approved and 'VIDEO' in reason else ('N/A' if approved else 'required')}",
            "",
            f"Compression saved {base.energy_savings_pct:.1f}% simulated energy.",
            f"Raw size: {base.input_bytes:,} bytes → compressed: "
            f"{base.compressed_bytes:,} bytes "
            f"(ratio {base.compression_ratio:.2f}×).",
            "",
        ]

        if not approved:
            lines += [
                "This content type was blocked by the media governance policy.",
                "In a real low-bandwidth deployment, this would prevent automatic",
                "transmission and require an explicit operator decision.",
            ]
        else:
            lines += [
                "In a real low-bandwidth system (satellite, mesh, emergency comms),",
                f"compression savings of {base.energy_savings_pct:.1f}% directly reduce",
                "battery drain, transmission cost, and channel occupancy.",
                "The provenance hash provides tamper-evident attribution.",
            ]

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pseudo_random_bytes(count: int, seed: int) -> bytes:
    """Generate deterministic pseudo-random bytes for simulation.

    Uses a simple linear congruential generator seeded with *seed*.
    Output is reproducible but statistically varied — suitable for
    testing compression behavior on non-compressible data.
    """
    # Produce bytes that BHL compression cannot easily reduce,
    # simulating real binary media content.
    import hashlib

    chunks: list[bytes] = []
    state = seed.to_bytes(4, "big")
    while sum(len(c) for c in chunks) < count:
        state = hashlib.sha256(state).digest()
        chunks.append(state)

    return b"".join(chunks)[:count]
