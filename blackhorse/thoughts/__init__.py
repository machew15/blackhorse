"""
Stage PoT — Blackhorse Proof of Thought
========================================
Cryptographically timestamped reasoning records.

Not proof of what was decided. Proof of WHY.

Quick start::

    from pathlib import Path
    from blackhorse.thoughts import ThoughtWriter, GovernanceLevel

    writer = ThoughtWriter(Path("thoughts/"))
    thought = writer.create(
        slug="why-bhl-not-utf8",
        author="human",
        stage_context="Protocol Stage 2",
        decision="BHL uses a custom symbol table, not UTF-8",
        reasoning="...",
        tags=["encoding", "design"],
    )
    assert writer.verify(thought)
    assert thought.integrity.bhl_encoded  # BHL Stage 2 confirmed live
"""

from .engine import (
    GovernanceLevel,
    AuthorType,
    ThoughtHeader,
    ThoughtIntegrity,
    Thought,
    ThoughtManifest,
    ThoughtWriter,
)
from .remediation import RemediationLayer, RemediationFlag

__all__ = [
    "GovernanceLevel",
    "AuthorType",
    "ThoughtHeader",
    "ThoughtIntegrity",
    "Thought",
    "ThoughtManifest",
    "ThoughtWriter",
    "RemediationLayer",
    "RemediationFlag",
]
