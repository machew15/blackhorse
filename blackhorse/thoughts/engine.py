"""
Blackhorse Proof of Thought (PoT) — thoughts/ module
=====================================================
Cryptographically timestamped reasoning records.

Not proof of what was decided. Proof of WHY.

AI Assistants: See docs/THOUGHT_SPEC.md for the full specification.
This module is self-contained; BHL encoding (Stage 2) is wired in when
available, but falls back gracefully if imported outside the package.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# BHL integration — Stage 2 is available; import opportunistically.
# bhl_encoded = True on any ThoughtIntegrity means the SHA-256 hash was
# verified to survive a BHL encode → decode round-trip, confirming the
# encoding layer is intact at the moment the thought was sealed.
# ---------------------------------------------------------------------------
try:
    from blackhorse.language import BHLEncoder, BHLDecoder
    _BHL_AVAILABLE = True
except ImportError:  # allow engine.py to be used standalone
    _BHL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Governance Levels
# ---------------------------------------------------------------------------

class GovernanceLevel(str, Enum):
    STANDARD  = "standard"   # Normal design decision
    ELEVATED  = "elevated"   # Significant downstream impact
    CRITICAL  = "critical"   # Security, compliance, or sovereignty impact
    SOVEREIGN = "sovereign"  # Fundamental — cannot be changed without explicit supersession


# ---------------------------------------------------------------------------
# Author Types
# ---------------------------------------------------------------------------

class AuthorType(str, Enum):
    HUMAN         = "human"
    COLLABORATIVE = "collaborative"

    @classmethod
    def ai(cls, model_name: str) -> str:
        """Return an AI author string, e.g. ``'ai:claude-4.6-sonnet'``."""
        return f"ai:{model_name}"


# ---------------------------------------------------------------------------
# ThoughtHeader
# ---------------------------------------------------------------------------

@dataclass
class ThoughtHeader:
    thought_id:           str             # Zero-padded sequence: "0001"
    slug:                 str             # kebab-case: "why-bhl-not-utf8"
    author:               str             # "human" | "ai:ModelName" | "collaborative"
    timestamp_iso:        str             # ISO 8601 UTC
    stage_context:        str             # e.g. "Protocol Stage 2"
    decision:             str             # One-line summary of what was decided
    tags:                 list[str]       # Searchable tags
    remediation_required: bool = False   # Triggers remediation layer if True
    governance_level:     GovernanceLevel = GovernanceLevel.STANDARD
    supersedes:           Optional[str] = None  # thought_id this supersedes (SOVEREIGN only)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_text(self) -> str:
        tags_str = ", ".join(self.tags)
        lines = [
            f"thought_id: {self.thought_id}",
            f"slug: {self.slug}",
            f"author: {self.author}",
            f"timestamp_iso: {self.timestamp_iso}",
            f"stage_context: {self.stage_context}",
            f"decision: {self.decision}",
            f"tags: {tags_str}",
            f"remediation_required: {str(self.remediation_required).lower()}",
            f"governance_level: {self.governance_level.value}",
        ]
        if self.supersedes:
            lines.append(f"supersedes: {self.supersedes}")
        return "\n".join(lines)

    @classmethod
    def from_text(cls, text: str) -> "ThoughtHeader":
        data: dict[str, str] = {}
        for line in text.strip().splitlines():
            if ": " in line:
                key, _, value = line.partition(": ")
                data[key.strip()] = value.strip()
        return cls(
            thought_id=data["thought_id"],
            slug=data["slug"],
            author=data["author"],
            timestamp_iso=data["timestamp_iso"],
            stage_context=data["stage_context"],
            decision=data["decision"],
            tags=[t.strip() for t in data.get("tags", "").split(",") if t.strip()],
            remediation_required=data.get("remediation_required", "false") == "true",
            governance_level=GovernanceLevel(data.get("governance_level", "standard")),
            supersedes=data.get("supersedes"),
        )


# ---------------------------------------------------------------------------
# ThoughtIntegrity
# ---------------------------------------------------------------------------

@dataclass
class ThoughtIntegrity:
    sha256:          str   # SHA-256 of header + reasoning (hex, 64 chars)
    sha3_512:        str   # SHA-3-512 of header + reasoning (hex, 128 chars)
    bhl_encoded:     bool  # True if the sha256 digest survived a BHL round-trip
    manifest_entry:  str   # "THOUGHTS.manifest line N"
    signed_at:       str   # ISO 8601 UTC

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_text(self) -> str:
        return "\n".join([
            f"sha256: {self.sha256}",
            f"sha3_512: {self.sha3_512}",
            f"bhl_encoded: {str(self.bhl_encoded).lower()}",
            f"manifest_entry: {self.manifest_entry}",
            f"signed_at: {self.signed_at}",
        ])

    @classmethod
    def from_text(cls, text: str) -> "ThoughtIntegrity":
        data: dict[str, str] = {}
        for line in text.strip().splitlines():
            if ": " in line:
                key, _, value = line.partition(": ")
                data[key.strip()] = value.strip()
        return cls(
            sha256=data["sha256"],
            sha3_512=data["sha3_512"],
            bhl_encoded=data.get("bhl_encoded", "false") == "true",
            manifest_entry=data["manifest_entry"],
            signed_at=data["signed_at"],
        )


# ---------------------------------------------------------------------------
# Thought
# ---------------------------------------------------------------------------

@dataclass
class Thought:
    """
    A single Proof of Thought record.

    Contains a structured header, free-form reasoning, and a sealed
    integrity block (hashes + BHL verification flag + manifest reference).
    """

    header:    ThoughtHeader
    reasoning: str                        # Free-form. No rules. Write what you thought.
    integrity: Optional[ThoughtIntegrity] = None

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_file_text(self) -> str:
        """Serialize to ``.thought`` file format (header / reasoning / integrity)."""
        parts = [self.header.to_text(), "---", self.reasoning.strip()]
        if self.integrity:
            parts.extend(["---", self.integrity.to_text()])
        return "\n".join(parts) + "\n"

    @classmethod
    def from_file_text(cls, text: str) -> "Thought":
        """Parse a ``.thought`` file back into a ``Thought`` object."""
        sections = text.split("\n---\n")
        if len(sections) < 2:
            raise ValueError("Invalid .thought file: missing '---' delimiter")
        header    = ThoughtHeader.from_text(sections[0])
        reasoning = sections[1].strip()
        integrity = ThoughtIntegrity.from_text(sections[2]) if len(sections) > 2 else None
        return cls(header=header, reasoning=reasoning, integrity=integrity)

    # ------------------------------------------------------------------
    # Integrity
    # ------------------------------------------------------------------

    def compute_hashes(self) -> tuple[str, str]:
        """
        Compute SHA-256 and SHA-3-512 of (header text + '\\n---\\n' + reasoning).

        This is the canonical content that is hashed — the integrity block
        itself is intentionally excluded so the hash can be inserted after
        the fact without changing the digest.
        """
        content = (self.header.to_text() + "\n---\n" + self.reasoning).encode("utf-8")
        sha256  = hashlib.sha256(content).hexdigest()
        sha3    = hashlib.sha3_512(content).hexdigest()
        return sha256, sha3


# ---------------------------------------------------------------------------
# ThoughtManifest — append-only chain
# ---------------------------------------------------------------------------

class ThoughtManifest:
    """
    Append-only chain of all ``.thought`` files.

    Each line: ``thought_id | timestamp_iso | sha256 | slug | governance_level``

    A SHA-256 of the entire manifest is stored alongside in
    ``THOUGHTS.manifest.sha256``. Altering any entry changes the
    manifest content, which changes that digest, breaking verification.
    """

    MANIFEST_FILENAME      = "THOUGHTS.manifest"
    MANIFEST_HASH_FILENAME = "THOUGHTS.manifest.sha256"

    def __init__(self, manifest_path: Path) -> None:
        self.path       = manifest_path
        self.hash_path  = manifest_path.with_suffix(".sha256")
        self._entries:  list[str] = []
        if manifest_path.exists():
            raw = manifest_path.read_text(encoding="utf-8").strip()
            self._entries = raw.splitlines() if raw else []

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def append(self, thought: Thought, sha256: str) -> str:
        """Append a thought and return the manifest entry string."""
        entry = " | ".join([
            thought.header.thought_id,
            thought.header.timestamp_iso,
            sha256,
            thought.header.slug,
            thought.header.governance_level.value,
        ])
        self._entries.append(entry)
        self._write()
        return f"{self.MANIFEST_FILENAME} line {len(self._entries)}"

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_chain(self) -> bool:
        """
        Verify the manifest is intact.

        Reads the manifest from disk, recomputes its SHA-256, and compares
        against the stored digest in ``THOUGHTS.manifest.sha256``.
        Also confirms the in-memory entry list matches the on-disk content.
        """
        if not self.path.exists():
            return True  # empty manifest is valid

        if not self.hash_path.exists():
            return False  # manifest exists but no stored digest — tampered

        on_disk   = self.path.read_text(encoding="utf-8")
        stored    = self.hash_path.read_text(encoding="utf-8").strip()
        computed  = hashlib.sha256(on_disk.encode("utf-8")).hexdigest()

        if stored != computed:
            return False  # manifest content has changed since last write

        disk_lines = on_disk.strip().splitlines() if on_disk.strip() else []
        return disk_lines == self._entries

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_by_governance(self, level: GovernanceLevel) -> list[str]:
        """Return all manifest entries at a given governance level."""
        return [e for e in self._entries if e.endswith(f"| {level.value}")]

    @property
    def count(self) -> int:
        return len(self._entries)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _write(self) -> None:
        content = "\n".join(self._entries) + "\n"
        self.path.write_text(content, encoding="utf-8")
        # Seal the manifest with a SHA-256 digest so verify_chain() can detect tampering.
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.hash_path.write_text(digest, encoding="utf-8")


# ---------------------------------------------------------------------------
# ThoughtWriter — main interface
# ---------------------------------------------------------------------------

class ThoughtWriter:
    """
    Create and persist ``.thought`` files.

    Usage::

        writer = ThoughtWriter(thoughts_dir=Path("thoughts/"))

        thought = writer.create(
            slug="why-bhl-not-utf8",
            author="human",
            stage_context="Protocol Stage 2",
            decision="BHL uses a custom symbol table, not UTF-8",
            reasoning="I considered UTF-8 because it's universal...",
            tags=["encoding", "design"],
            governance_level=GovernanceLevel.STANDARD,
        )
    """

    # kebab-case: starts with a letter, followed by lowercase letters, digits, hyphens.
    # Dots are not valid kebab-case separators.
    _SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")

    def __init__(self, thoughts_dir: Path) -> None:
        self.dir = thoughts_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest = ThoughtManifest(
            thoughts_dir / ThoughtManifest.MANIFEST_FILENAME
        )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        slug: str,
        author: str,
        stage_context: str,
        decision: str,
        reasoning: str,
        tags: list[str],
        governance_level: GovernanceLevel = GovernanceLevel.STANDARD,
        remediation_required: bool = False,
        supersedes: Optional[str] = None,
    ) -> Thought:
        """
        Create, hash, manifest, and persist a new ``.thought`` file.

        The BHL encoding layer (Stage 2) is invoked if available: the
        SHA-256 digest is run through ``BHLEncoder → BHLDecoder`` and the
        result compared to the original bytes. If the round-trip passes,
        ``ThoughtIntegrity.bhl_encoded`` is set to ``True``, serving as a
        live integration test of the encoding layer embedded in every seal.
        """
        self._validate_slug(slug)
        self._validate_supersedes(governance_level, supersedes)

        thought_id = str(self.manifest.count + 1).zfill(4)
        timestamp  = datetime.now(timezone.utc).isoformat(timespec="seconds")

        header = ThoughtHeader(
            thought_id=thought_id,
            slug=slug,
            author=author,
            timestamp_iso=timestamp,
            stage_context=stage_context,
            decision=decision,
            tags=tags,
            remediation_required=remediation_required,
            governance_level=governance_level,
            supersedes=supersedes,
        )
        thought = Thought(header=header, reasoning=reasoning)

        sha256, sha3 = thought.compute_hashes()
        manifest_entry = self.manifest.append(thought, sha256)

        thought.integrity = ThoughtIntegrity(
            sha256=sha256,
            sha3_512=sha3,
            bhl_encoded=self._verify_bhl(sha256),
            manifest_entry=manifest_entry,
            signed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

        filename = f"{thought_id}_{slug}.thought"
        (self.dir / filename).write_text(thought.to_file_text(), encoding="utf-8")

        if remediation_required or governance_level in (
            GovernanceLevel.CRITICAL, GovernanceLevel.SOVEREIGN
        ):
            self._flag_for_remediation(thought)

        return thought

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(self, thought_id: str) -> Thought:
        """Read a ``.thought`` file by its zero-padded ID."""
        matches = sorted(self.dir.glob(f"{thought_id}_*.thought"))
        if not matches:
            raise FileNotFoundError(f"No thought found with ID {thought_id!r}")
        return Thought.from_file_text(matches[0].read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    def verify(self, thought: Thought) -> bool:
        """Return True if the thought's integrity hashes match its current content."""
        if not thought.integrity:
            return False
        sha256, sha3 = thought.compute_hashes()
        return (
            sha256 == thought.integrity.sha256
            and sha3 == thought.integrity.sha3_512
        )

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_all(self) -> list[Path]:
        """Return all ``.thought`` files in sequence order."""
        return sorted(self.dir.glob("*.thought"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_bhl(sha256_hex: str) -> bool:
        """
        Run the SHA-256 hex digest through a BHL encode→decode round-trip.

        Returns ``True`` if the round-trip is lossless (BHL Stage 2 is
        functioning correctly). Returns ``False`` if BHL is unavailable
        or the round-trip fails.
        """
        if not _BHL_AVAILABLE:
            return False
        try:
            data     = sha256_hex.encode("utf-8")
            encoded  = BHLEncoder().encode_bytes(data)
            decoded  = BHLDecoder().decode_bytes(encoded)
            return decoded == data
        except Exception:
            return False

    @classmethod
    def _validate_slug(cls, slug: str) -> None:
        if not cls._SLUG_RE.match(slug):
            raise ValueError(
                f"Slug must be kebab-case (lowercase letters, digits, hyphens; "
                f"must start with a letter): {slug!r}"
            )

    @staticmethod
    def _validate_supersedes(level: GovernanceLevel, supersedes: Optional[str]) -> None:
        if supersedes and level is not GovernanceLevel.SOVEREIGN:
            raise ValueError(
                "Only SOVEREIGN thoughts may supersede another thought. "
                f"Got governance_level={level.value!r}"
            )

    def _flag_for_remediation(self, thought: Thought) -> None:
        """
        Write a remediation flag file for this thought.

        The remediation layer picks this up — it does NOT fix anything.
        It flags and routes. Fixing is a human (or sovereign AI) decision.
        """
        flag_dir = self.dir.parent / "remediation" / "flags"
        flag_dir.mkdir(parents=True, exist_ok=True)
        flag_file = flag_dir / f"{thought.header.thought_id}_{thought.header.slug}.flag"
        payload = {
            "thought_id":       thought.header.thought_id,
            "slug":             thought.header.slug,
            "governance_level": thought.header.governance_level.value,
            "flagged_at":       datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reason":           (
                "remediation_required"
                if thought.header.remediation_required
                else f"governance_level:{thought.header.governance_level.value}"
            ),
            "status":   "open",
            "resolved": False,
        }
        flag_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
