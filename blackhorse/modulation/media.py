"""
SIMULATION ONLY — Media content-type awareness, attestation, and provenance.

Files are read locally, hashed, attested, and analyzed. Nothing leaves the
machine. No media is transmitted. This layer adds content-type detection,
per-type governance constraints, and signed provenance receipts to the
modulation simulation pipeline.

Video content always requires explicit human operator approval before it
can be marked as cleared — it is never auto-approved by this module.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from blackhorse.compression import compress
from blackhorse.crypto.signing import BHLSigner
from blackhorse.modulation.governance import ModulationConstraints


# ---------------------------------------------------------------------------
# MediaType
# ---------------------------------------------------------------------------


class MediaType(Enum):
    """Content-type categories for media governance.

    Detection order: file extension → magic bytes → UTF-8 probe → UNKNOWN.
    """

    TEXT     = "text"
    IMAGE    = "image"
    AUDIO    = "audio"
    VIDEO    = "video"
    DOCUMENT = "document"
    UNKNOWN  = "unknown"


# ---------------------------------------------------------------------------
# InterruptCommand / InterruptHandler
# ---------------------------------------------------------------------------


@dataclass
class InterruptCommand:
    """A signed operator command for manual approval or rejection of media.

    Used to create a verifiable, auditable trail of human decisions about
    media content that cannot be automatically approved by policy.
    """

    attestation_id: str
    command: str          # "APPROVE" or "REJECT"
    operator_id: str
    notes: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class InterruptHandler:
    """Handles human operator interrupt commands for media governance.

    Produces a signed receipt bytes object that is stored as
    ``MediaAttestation.approval_receipt``. The receipt can be verified
    later using ``BHLSigner.verify_and_extract()``.
    """

    def __init__(
        self, signing_key: bytes, operator_id: str = "operator"
    ) -> None:
        self._signing_key = signing_key
        self._operator_id = operator_id

    def handle(self, command: InterruptCommand) -> bytes:
        """Process *command* and return a signed receipt bytes object."""
        payload = json.dumps(
            {
                "type": "INTERRUPT_RECEIPT",
                "attestation_id": command.attestation_id,
                "command": command.command,
                "operator_id": command.operator_id,
                "notes": command.notes,
                "timestamp": command.timestamp.isoformat(),
            },
            separators=(",", ":"),
        ).encode()
        return BHLSigner().sign(payload, self._signing_key)

    @property
    def operator_id(self) -> str:
        return self._operator_id


# ---------------------------------------------------------------------------
# MediaConstraints
# ---------------------------------------------------------------------------


@dataclass
class MediaConstraints(ModulationConstraints):
    """Per-media-type governance constraints extending ModulationConstraints.

    Size limits are in bytes. Type allowances control which media categories
    can pass automatic governance. Video always requires human approval.
    """

    max_image_bytes: int = 10_485_760      # 10 MB
    max_audio_bytes: int = 52_428_800      # 50 MB
    max_video_bytes: int = 104_857_600     # 100 MB
    max_document_bytes: int = 10_485_760   # 10 MB

    allowed_media_types: List[str] = field(
        default_factory=lambda: ["text", "image", "audio", "document"]
    )
    """video is intentionally absent — it requires human approval."""

    require_provenance: bool = True
    """All media outputs must carry a signed provenance receipt."""

    video_requires_human_approval: bool = True
    """Video content never auto-approves. Operator must call approve()."""


# ---------------------------------------------------------------------------
# MediaAttestation
# ---------------------------------------------------------------------------


@dataclass
class MediaAttestation:
    """Signed provenance record for a locally-analyzed media file.

    The ``signature`` field is HMAC-SHA256 over the canonical serialization
    of all other fields. Verify integrity with ``MediaAttestor.verify()``.

    SIMULATION ONLY — this is a local provenance record, not a transmission
    clearance or broadcast authorization.
    """

    attestation_id: str         # UUID string
    media_type: MediaType
    filename: str               # original filename, no path
    content_hash: str           # SHA-256 hex of raw media bytes
    compressed_hash: str        # SHA-256 hex of BHL-compressed bytes
    size_bytes: int
    compressed_size_bytes: int
    compression_ratio: float
    created_at: datetime        # UTC
    attested_by: str            # node_id of attesting node
    signature: bytes            # HMAC-SHA256 over all above fields
    human_approved: bool = False
    approval_receipt: Optional[bytes] = None


# ---------------------------------------------------------------------------
# MediaAttestor
# ---------------------------------------------------------------------------

# Magic byte signatures for binary format detection.
_MAGIC = {
    b"\xff\xd8\xff":    MediaType.IMAGE,    # JPEG
    b"\x89PNG":         MediaType.IMAGE,    # PNG
    b"GIF8":            MediaType.IMAGE,    # GIF
    b"ID3":             MediaType.AUDIO,    # MP3 with ID3 tag
    b"\xff\xfb":        MediaType.AUDIO,    # MP3 raw frame
    b"%PDF":            MediaType.DOCUMENT, # PDF
}

_EXT_MAP = {
    ".jpg":  MediaType.IMAGE,
    ".jpeg": MediaType.IMAGE,
    ".png":  MediaType.IMAGE,
    ".gif":  MediaType.IMAGE,
    ".mp3":  MediaType.AUDIO,
    ".wav":  MediaType.AUDIO,
    ".aac":  MediaType.AUDIO,
    ".mp4":  MediaType.VIDEO,
    ".mov":  MediaType.VIDEO,
    ".avi":  MediaType.VIDEO,
    ".mkv":  MediaType.VIDEO,
    ".pdf":  MediaType.DOCUMENT,
    ".doc":  MediaType.DOCUMENT,
    ".docx": MediaType.DOCUMENT,
    ".txt":  MediaType.TEXT,
    ".md":   MediaType.TEXT,
    ".csv":  MediaType.TEXT,
    ".json": MediaType.TEXT,
    ".xml":  MediaType.TEXT,
}


class MediaAttestor:
    """Attests, verifies, and serializes media provenance records.

    All operations are local — no network calls, no uploads, no transmission.
    The signed ``MediaAttestation`` is a provenance receipt that can be
    stored alongside the analyzed file or shared for third-party verification.

    SIMULATION ONLY — attestation is for data integrity research, not
    broadcast authorization or spectrum licensing.
    """

    def __init__(
        self,
        node_id: str,
        signing_key: bytes,
        interrupt_handler: Optional[InterruptHandler] = None,
        constraints: Optional[MediaConstraints] = None,
    ) -> None:
        self._node_id = node_id
        self._signing_key = signing_key
        self._interrupt_handler = interrupt_handler
        self._constraints = constraints or MediaConstraints()

    # ------------------------------------------------------------------
    # Type detection
    # ------------------------------------------------------------------

    def detect_type(self, filename: str, data: bytes) -> MediaType:
        """Detect media type from file extension, then magic bytes.

        Detection order:
          1. File extension (case-insensitive).
          2. Magic bytes at offset 0 (JPEG, PNG, GIF, MP3, PDF).
          3. MP4: ``ftyp`` at offset 4.
          4. Valid UTF-8 → TEXT.
          5. Fallback → UNKNOWN.
        """
        # Extension check — strip path, lowercase.
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
            if ext in _EXT_MAP:
                return _EXT_MAP[ext]

        # Magic bytes at offset 0.
        for magic, mtype in _MAGIC.items():
            if data[: len(magic)] == magic:
                return mtype

        # MP4: "ftyp" at offset 4.
        if len(data) >= 8 and data[4:8] == b"ftyp":
            return MediaType.VIDEO

        # UTF-8 probe.
        try:
            data.decode("utf-8")
            return MediaType.TEXT
        except (UnicodeDecodeError, ValueError):
            pass

        return MediaType.UNKNOWN

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def attest(
        self, data: bytes, filename: str, signing_key: bytes
    ) -> MediaAttestation:
        """Produce a signed MediaAttestation for *data*.

        Steps:
          1. Detect content type.
          2. Compute SHA-256 of raw bytes (content_hash).
          3. Compress via BHL; compute SHA-256 of compressed bytes.
          4. Sign all attestation fields with HMAC-SHA256.
          5. If VIDEO and video_requires_human_approval: set human_approved=False.

        Returns a signed MediaAttestation. Does NOT transmit anything.
        """
        media_type = self.detect_type(filename, data)

        content_hash = hashlib.sha256(data).hexdigest()
        compressed = compress(data)
        compressed_hash = hashlib.sha256(compressed).hexdigest()

        # Round before signing so that verify() can reproduce the same bytes.
        ratio = round(len(data) / len(compressed), 4) if compressed else 0.0
        att_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)

        # Build the canonical payload and sign it.
        sig_payload = self._build_sig_payload(
            attestation_id=att_id,
            media_type=media_type,
            filename=filename,
            content_hash=content_hash,
            compressed_hash=compressed_hash,
            size_bytes=len(data),
            compressed_size_bytes=len(compressed),
            compression_ratio=ratio,
            created_at=created_at,
            attested_by=self._node_id,
        )
        signature = self._hmac(sig_payload, signing_key)

        attestation = MediaAttestation(
            attestation_id=att_id,
            media_type=media_type,
            filename=filename,
            content_hash=content_hash,
            compressed_hash=compressed_hash,
            size_bytes=len(data),
            compressed_size_bytes=len(compressed),
            compression_ratio=ratio,
            created_at=created_at,
            attested_by=self._node_id,
            signature=signature,
            human_approved=False,
            approval_receipt=None,
        )

        if media_type == MediaType.VIDEO and self._constraints.video_requires_human_approval:
            # Video never auto-approves.  Log clearly.
            print(
                "[MEDIA GOVERNANCE] VIDEO content detected. "
                "human_approved=False. "
                "Call MediaAttestor.approve() for explicit operator sign-off."
            )

        return attestation

    def approve(
        self,
        attestation: MediaAttestation,
        operator_signing_key: bytes,
    ) -> MediaAttestation:
        """Explicitly approve a media attestation as a human operator.

        Generates a signed approval receipt via the configured
        InterruptHandler (or a minimal inline receipt if none is set).
        Sets ``human_approved=True`` and attaches ``approval_receipt``.

        Returns the updated attestation.
        """
        command = InterruptCommand(
            attestation_id=attestation.attestation_id,
            command="APPROVE",
            operator_id=(
                self._interrupt_handler.operator_id
                if self._interrupt_handler
                else "operator"
            ),
            notes="Operator explicit sign-off",
        )

        if self._interrupt_handler:
            receipt = self._interrupt_handler.handle(command)
        else:
            # Minimal inline receipt when no InterruptHandler configured.
            payload = json.dumps(
                {
                    "type": "INLINE_APPROVAL",
                    "attestation_id": command.attestation_id,
                    "command": command.command,
                    "timestamp": command.timestamp.isoformat(),
                },
                separators=(",", ":"),
            ).encode()
            receipt = BHLSigner().sign(payload, operator_signing_key)

        attestation.human_approved = True
        attestation.approval_receipt = receipt
        return attestation

    def verify(
        self, attestation: MediaAttestation, data: bytes, signing_key: bytes
    ) -> bool:
        """Verify that *data* matches the attested content and the signature is valid.

        Recomputes the SHA-256 of *data* and the HMAC-SHA256 of the
        attestation fields. Returns True only if BOTH match — i.e. the
        data has not been modified AND the attestation was signed by the
        expected key.
        """
        # Data integrity check.
        expected_hash = hashlib.sha256(data).hexdigest()
        if expected_hash != attestation.content_hash:
            return False

        # Signature check.
        sig_payload = self._build_sig_payload(
            attestation_id=attestation.attestation_id,
            media_type=attestation.media_type,
            filename=attestation.filename,
            content_hash=attestation.content_hash,
            compressed_hash=attestation.compressed_hash,
            size_bytes=attestation.size_bytes,
            compressed_size_bytes=attestation.compressed_size_bytes,
            compression_ratio=attestation.compression_ratio,
            created_at=attestation.created_at,
            attested_by=attestation.attested_by,
        )
        expected_sig = self._hmac(sig_payload, signing_key)
        return hmac.compare_digest(expected_sig, attestation.signature)

    def serialize(self, attestation: MediaAttestation) -> bytes:
        """Serialize *attestation* to a signed packet bytes object.

        Produces a BHLSigner-signed packet over the JSON representation
        of the attestation. The result is a portable, verifiable provenance
        receipt that can be stored or shared for third-party verification.

        SIMULATION ONLY — this is a local record, not a transmission packet.
        """
        payload = json.dumps(
            {
                "attestation_id": attestation.attestation_id,
                "media_type": attestation.media_type.value,
                "filename": attestation.filename,
                "content_hash": attestation.content_hash,
                "compressed_hash": attestation.compressed_hash,
                "size_bytes": attestation.size_bytes,
                "compressed_size_bytes": attestation.compressed_size_bytes,
                "compression_ratio": attestation.compression_ratio,
                "created_at": attestation.created_at.isoformat(),
                "attested_by": attestation.attested_by,
                "human_approved": attestation.human_approved,
                "has_approval_receipt": attestation.approval_receipt is not None,
            },
            separators=(",", ":"),
        ).encode()
        return BHLSigner().sign(payload, self._signing_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_sig_payload(
        *,
        attestation_id: str,
        media_type: MediaType,
        filename: str,
        content_hash: str,
        compressed_hash: str,
        size_bytes: int,
        compressed_size_bytes: int,
        compression_ratio: float,
        created_at: datetime,
        attested_by: str,
    ) -> bytes:
        """Build the canonical bytes representation used for signing."""
        return json.dumps(
            {
                "attestation_id": attestation_id,
                "media_type": media_type.value,
                "filename": filename,
                "content_hash": content_hash,
                "compressed_hash": compressed_hash,
                "size_bytes": size_bytes,
                "compressed_size_bytes": compressed_size_bytes,
                "compression_ratio": compression_ratio,
                "created_at": created_at.isoformat(),
                "attested_by": attested_by,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()

    @staticmethod
    def _hmac(data: bytes, key: bytes) -> bytes:
        """Compute HMAC-SHA256 of *data* under *key*."""
        return hmac.new(key, data, hashlib.sha256).digest()
