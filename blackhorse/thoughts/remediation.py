"""
Blackhorse Proof of Thought — Remediation Layer
================================================
Flags route here. Resolution stays human.

The remediation layer does three things:
  1. List open flags (what needs attention)
  2. Resolve flags (acknowledge + document, never silently close)
  3. Summarise the remediation state of the repository

A flag is NEVER deleted. It is resolved with a written resolution note
that becomes part of the audit trail. Open + resolved flags together
form the complete remediation record.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class RemediationFlag:
    """In-memory representation of a ``.flag`` file."""
    thought_id:       str
    slug:             str
    governance_level: str
    flagged_at:       str
    reason:           str
    status:           str          # "open" | "resolved"
    resolved:         bool
    resolution_note:  Optional[str] = None
    resolved_by:      Optional[str] = None
    resolved_at:      Optional[str] = None
    path:             Optional[Path] = None

    @classmethod
    def from_file(cls, path: Path) -> "RemediationFlag":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            thought_id=data["thought_id"],
            slug=data["slug"],
            governance_level=data["governance_level"],
            flagged_at=data["flagged_at"],
            reason=data["reason"],
            status=data.get("status", "open"),
            resolved=data.get("resolved", False),
            resolution_note=data.get("resolution_note"),
            resolved_by=data.get("resolved_by"),
            resolved_at=data.get("resolved_at"),
            path=path,
        )

    def to_dict(self) -> dict:
        d = {
            "thought_id":       self.thought_id,
            "slug":             self.slug,
            "governance_level": self.governance_level,
            "flagged_at":       self.flagged_at,
            "reason":           self.reason,
            "status":           self.status,
            "resolved":         self.resolved,
        }
        if self.resolution_note:
            d["resolution_note"] = self.resolution_note
        if self.resolved_by:
            d["resolved_by"] = self.resolved_by
        if self.resolved_at:
            d["resolved_at"] = self.resolved_at
        return d


class RemediationLayer:
    """
    Interface for listing and resolving remediation flags.

    Usage::

        layer = RemediationLayer(flags_dir=Path("remediation/flags"))

        # See what needs attention
        open_flags = layer.list_open()

        # Acknowledge and document a resolution
        layer.resolve(
            thought_id="0003",
            resolution_note="Reviewed with security team. Risk accepted.",
            resolved_by="human",
        )

        # Overview
        print(layer.summary())
    """

    def __init__(self, flags_dir: Path) -> None:
        self.dir = flags_dir
        self.dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_all(self) -> list[RemediationFlag]:
        """Return all flags (open and resolved) in thought_id order."""
        return sorted(
            (RemediationFlag.from_file(p) for p in self.dir.glob("*.flag")),
            key=lambda f: f.thought_id,
        )

    def list_open(self) -> list[RemediationFlag]:
        """Return flags with status == 'open'."""
        return [f for f in self.list_all() if not f.resolved]

    def list_resolved(self) -> list[RemediationFlag]:
        """Return flags with status == 'resolved'."""
        return [f for f in self.list_all() if f.resolved]

    # ------------------------------------------------------------------
    # Resolve
    # ------------------------------------------------------------------

    def resolve(
        self,
        thought_id: str,
        resolution_note: str,
        resolved_by: str = "human",
    ) -> RemediationFlag:
        """
        Resolve an open flag.

        Writes the resolution note, ``resolved_by``, and ``resolved_at``
        back into the ``.flag`` file. The file is updated in place —
        never deleted.

        Raises ``FileNotFoundError`` if the flag does not exist.
        Raises ``ValueError`` if the flag is already resolved.
        """
        matches = sorted(self.dir.glob(f"{thought_id}_*.flag"))
        if not matches:
            raise FileNotFoundError(
                f"No remediation flag found for thought_id {thought_id!r}"
            )
        flag = RemediationFlag.from_file(matches[0])

        if flag.resolved:
            raise ValueError(
                f"Flag for thought {thought_id!r} is already resolved. "
                "Create a superseding SOVEREIGN thought to revisit the decision."
            )

        flag.status          = "resolved"
        flag.resolved        = True
        flag.resolution_note = resolution_note
        flag.resolved_by     = resolved_by
        flag.resolved_at     = datetime.now(timezone.utc).isoformat(timespec="seconds")

        if flag.path:
            flag.path.write_text(
                json.dumps(flag.to_dict(), indent=2), encoding="utf-8"
            )
        return flag

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """
        Return a dict summarising the remediation state.

        Intended for dashboards, CI checks, and health endpoints.
        A CI gate might reject merges when ``open_critical > 0``.
        """
        all_flags = self.list_all()
        open_flags = [f for f in all_flags if not f.resolved]

        by_level: dict[str, int] = {}
        for flag in open_flags:
            by_level[flag.governance_level] = by_level.get(flag.governance_level, 0) + 1

        return {
            "total":           len(all_flags),
            "open":            len(open_flags),
            "resolved":        len(all_flags) - len(open_flags),
            "open_by_level":   by_level,
            "open_critical":   by_level.get("critical", 0),
            "open_sovereign":  by_level.get("sovereign", 0),
            "needs_attention": len(open_flags) > 0,
        }
