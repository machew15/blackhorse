"""
Tests for the Blackhorse Proof of Thought (PoT) module.

Covers: ThoughtHeader, ThoughtIntegrity, Thought, ThoughtManifest,
        ThoughtWriter, RemediationLayer, and BHL integration.
"""

import json
import pytest
from pathlib import Path
from datetime import timezone

from blackhorse.thoughts import (
    GovernanceLevel,
    AuthorType,
    ThoughtHeader,
    ThoughtIntegrity,
    Thought,
    ThoughtManifest,
    ThoughtWriter,
    RemediationLayer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_thoughts(tmp_path: Path) -> ThoughtWriter:
    return ThoughtWriter(tmp_path / "thoughts")


@pytest.fixture
def basic_thought(tmp_thoughts: ThoughtWriter) -> Thought:
    return tmp_thoughts.create(
        slug="test-decision",
        author="human",
        stage_context="Test Stage",
        decision="Use pytest for testing",
        reasoning="pytest has the best fixture system. It's the right call.",
        tags=["testing", "tooling"],
    )


# ---------------------------------------------------------------------------
# GovernanceLevel
# ---------------------------------------------------------------------------

class TestGovernanceLevel:
    def test_all_levels_exist(self):
        levels = {l.value for l in GovernanceLevel}
        assert levels == {"standard", "elevated", "critical", "sovereign"}

    def test_from_string(self):
        assert GovernanceLevel("critical") is GovernanceLevel.CRITICAL


# ---------------------------------------------------------------------------
# AuthorType
# ---------------------------------------------------------------------------

class TestAuthorType:
    def test_ai_helper(self):
        assert AuthorType.ai("claude-4.6-sonnet-high-thinking") == "ai:claude-4.6-sonnet-high-thinking"

    def test_human_value(self):
        assert AuthorType.HUMAN.value == "human"

    def test_collaborative_value(self):
        assert AuthorType.COLLABORATIVE.value == "collaborative"


# ---------------------------------------------------------------------------
# ThoughtHeader serialisation
# ---------------------------------------------------------------------------

class TestThoughtHeader:
    def _make_header(self, **overrides) -> ThoughtHeader:
        defaults = dict(
            thought_id="0001",
            slug="test-slug",
            author="human",
            timestamp_iso="2026-03-06T19:00:00+00:00",
            stage_context="Stage 1",
            decision="Test decision",
            tags=["a", "b"],
        )
        return ThoughtHeader(**{**defaults, **overrides})

    def test_to_text_contains_all_fields(self):
        h = self._make_header()
        text = h.to_text()
        assert "thought_id: 0001" in text
        assert "slug: test-slug" in text
        assert "author: human" in text
        assert "tags: a, b" in text
        assert "governance_level: standard" in text

    def test_round_trip(self):
        h = self._make_header(tags=["encoding", "design", "bhl"])
        restored = ThoughtHeader.from_text(h.to_text())
        assert restored.thought_id == h.thought_id
        assert restored.slug == h.slug
        assert restored.tags == h.tags
        assert restored.governance_level == h.governance_level

    def test_supersedes_only_in_text_when_set(self):
        h = self._make_header(
            governance_level=GovernanceLevel.SOVEREIGN,
            supersedes="0002",
        )
        text = h.to_text()
        assert "supersedes: 0002" in text

    def test_supersedes_absent_when_none(self):
        h = self._make_header()
        assert "supersedes" not in h.to_text()

    def test_remediation_required_round_trip(self):
        h = self._make_header(remediation_required=True)
        restored = ThoughtHeader.from_text(h.to_text())
        assert restored.remediation_required is True

    def test_empty_tags_round_trip(self):
        h = self._make_header(tags=[])
        restored = ThoughtHeader.from_text(h.to_text())
        assert restored.tags == []


# ---------------------------------------------------------------------------
# Thought hash computation
# ---------------------------------------------------------------------------

class TestThoughtHashing:
    def _make_thought(self, reasoning: str = "Some reasoning.") -> Thought:
        header = ThoughtHeader(
            thought_id="0001",
            slug="hash-test",
            author="human",
            timestamp_iso="2026-03-06T19:00:00+00:00",
            stage_context="Test",
            decision="Test",
            tags=["test"],
        )
        return Thought(header=header, reasoning=reasoning)

    def test_sha256_is_64_chars(self):
        sha256, _ = self._make_thought().compute_hashes()
        assert len(sha256) == 64

    def test_sha3_512_is_128_chars(self):
        _, sha3 = self._make_thought().compute_hashes()
        assert len(sha3) == 128

    def test_hashes_are_hex(self):
        sha256, sha3 = self._make_thought().compute_hashes()
        assert all(c in "0123456789abcdef" for c in sha256)
        assert all(c in "0123456789abcdef" for c in sha3)

    def test_same_content_gives_same_hash(self):
        t = self._make_thought("consistent reasoning")
        h1, h3a = t.compute_hashes()
        h2, h3b = t.compute_hashes()
        assert h1 == h2
        assert h3a == h3b

    def test_different_content_gives_different_hash(self):
        h1, _ = self._make_thought("reasoning A").compute_hashes()
        h2, _ = self._make_thought("reasoning B").compute_hashes()
        assert h1 != h2

    def test_integrity_not_included_in_hash(self):
        """Changing the integrity block must not change the content hash."""
        t = self._make_thought("stable reasoning")
        sha256_before, _ = t.compute_hashes()
        t.integrity = ThoughtIntegrity(
            sha256=sha256_before,
            sha3_512="x" * 128,
            bhl_encoded=True,
            manifest_entry="line 1",
            signed_at="2026-03-06T19:00:01+00:00",
        )
        sha256_after, _ = t.compute_hashes()
        assert sha256_before == sha256_after


# ---------------------------------------------------------------------------
# Thought serialisation round-trip
# ---------------------------------------------------------------------------

class TestThoughtSerialisation:
    def test_round_trip_without_integrity(self):
        header = ThoughtHeader(
            thought_id="0001",
            slug="no-integrity",
            author="human",
            timestamp_iso="2026-03-06T19:00:00+00:00",
            stage_context="Test",
            decision="Manually built thought",
            tags=["test"],
        )
        thought = Thought(header=header, reasoning="Some reasoning.", integrity=None)
        text = thought.to_file_text()
        restored = Thought.from_file_text(text)
        assert restored.header.slug == thought.header.slug
        assert restored.reasoning == thought.reasoning
        assert restored.integrity is None

    def test_round_trip_with_integrity(self, basic_thought: Thought):
        text = basic_thought.to_file_text()
        restored = Thought.from_file_text(text)
        assert restored.integrity is not None
        assert len(restored.integrity.sha256) == 64
        assert len(restored.integrity.sha3_512) == 128

    def test_missing_delimiter_raises(self):
        with pytest.raises(ValueError, match="---"):
            Thought.from_file_text("thought_id: 0001\nno delimiter here")


# ---------------------------------------------------------------------------
# ThoughtWriter
# ---------------------------------------------------------------------------

class TestThoughtWriter:
    def test_creates_thought_file(self, tmp_thoughts: ThoughtWriter):
        t = tmp_thoughts.create(
            slug="my-decision",
            author="human",
            stage_context="Stage 1",
            decision="Use SQLite",
            reasoning="It has zero dependencies and is battle-tested.",
            tags=["database"],
        )
        filepath = tmp_thoughts.dir / f"{t.header.thought_id}_{t.header.slug}.thought"
        assert filepath.exists()

    def test_thought_id_is_zero_padded(self, tmp_thoughts: ThoughtWriter):
        t = tmp_thoughts.create(
            slug="first-thought",
            author="human",
            stage_context="S1",
            decision="D",
            reasoning="R",
            tags=[],
        )
        assert t.header.thought_id == "0001"

    def test_sequence_increments(self, tmp_thoughts: ThoughtWriter):
        for slug in ["first", "second", "third"]:
            tmp_thoughts.create(
                slug=slug,
                author="human",
                stage_context="S",
                decision="D",
                reasoning="R",
                tags=[],
            )
        assert tmp_thoughts.manifest.count == 3

    def test_integrity_is_set(self, basic_thought: Thought):
        assert basic_thought.integrity is not None
        assert len(basic_thought.integrity.sha256) == 64

    def test_bhl_encoded_is_true(self, basic_thought: Thought):
        assert basic_thought.integrity is not None
        assert basic_thought.integrity.bhl_encoded is True

    def test_verify_passes_for_unaltered_thought(
        self, tmp_thoughts: ThoughtWriter, basic_thought: Thought
    ):
        assert tmp_thoughts.verify(basic_thought)

    def test_verify_fails_for_altered_reasoning(
        self, tmp_thoughts: ThoughtWriter, basic_thought: Thought
    ):
        basic_thought.reasoning = "TAMPERED reasoning."
        assert not tmp_thoughts.verify(basic_thought)

    def test_read_round_trip(self, tmp_thoughts: ThoughtWriter, basic_thought: Thought):
        restored = tmp_thoughts.read(basic_thought.header.thought_id)
        assert restored.header.slug == basic_thought.header.slug
        assert restored.reasoning == basic_thought.reasoning

    def test_invalid_slug_raises(self, tmp_thoughts: ThoughtWriter):
        with pytest.raises(ValueError, match="kebab-case"):
            tmp_thoughts.create(
                slug="Invalid_Slug.bad",
                author="human",
                stage_context="S",
                decision="D",
                reasoning="R",
                tags=[],
            )

    def test_slug_with_digit_raises(self, tmp_thoughts: ThoughtWriter):
        with pytest.raises(ValueError, match="kebab-case"):
            tmp_thoughts.create(
                slug="1-starts-with-digit",
                author="human",
                stage_context="S",
                decision="D",
                reasoning="R",
                tags=[],
            )

    def test_valid_slug_with_hyphens(self, tmp_thoughts: ThoughtWriter):
        t = tmp_thoughts.create(
            slug="why-bhl-not-utf8",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
        )
        assert t.header.slug == "why-bhl-not-utf8"

    def test_valid_slug_with_numbers(self, tmp_thoughts: ThoughtWriter):
        t = tmp_thoughts.create(
            slug="stage2-encoding",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
        )
        assert t.header.slug == "stage2-encoding"

    def test_supersedes_only_on_sovereign(self, tmp_thoughts: ThoughtWriter):
        with pytest.raises(ValueError, match="SOVEREIGN"):
            tmp_thoughts.create(
                slug="invalid-supersede",
                author="human",
                stage_context="S",
                decision="D",
                reasoning="R",
                tags=[],
                governance_level=GovernanceLevel.CRITICAL,
                supersedes="0001",
            )

    def test_sovereign_with_supersedes(self, tmp_thoughts: ThoughtWriter):
        t = tmp_thoughts.create(
            slug="superseding-thought",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            governance_level=GovernanceLevel.SOVEREIGN,
            supersedes="0001",
        )
        assert t.header.supersedes == "0001"

    def test_list_all_returns_sorted_paths(self, tmp_thoughts: ThoughtWriter):
        for slug in ["alpha", "beta", "gamma"]:
            tmp_thoughts.create(
                slug=slug,
                author="human",
                stage_context="S",
                decision="D",
                reasoning="R",
                tags=[],
            )
        paths = tmp_thoughts.list_all()
        names = [p.name for p in paths]
        assert names == sorted(names)

    def test_timestamp_is_utc_iso(self, basic_thought: Thought):
        ts = basic_thought.header.timestamp_iso
        assert "T" in ts
        assert ts.endswith("+00:00") or ts.endswith("Z")


# ---------------------------------------------------------------------------
# ThoughtManifest chain verification
# ---------------------------------------------------------------------------

class TestThoughtManifest:
    def test_empty_manifest_verifies(self, tmp_thoughts: ThoughtWriter):
        assert tmp_thoughts.manifest.verify_chain()

    def test_chain_verifies_after_creation(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="manifested",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
        )
        assert tmp_thoughts.manifest.verify_chain()

    def test_chain_verifies_after_multiple_entries(self, tmp_thoughts: ThoughtWriter):
        for slug in ["first", "second", "third"]:
            tmp_thoughts.create(
                slug=slug,
                author="human",
                stage_context="S",
                decision="D",
                reasoning="R",
                tags=[],
            )
        assert tmp_thoughts.manifest.verify_chain()

    def test_tampered_manifest_fails_verification(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="target",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
        )
        # Corrupt the manifest
        manifest_path = tmp_thoughts.manifest.path
        content = manifest_path.read_text()
        manifest_path.write_text(content + "INJECTED ENTRY\n")
        assert not tmp_thoughts.manifest.verify_chain()

    def test_get_by_governance(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="standard-one",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            governance_level=GovernanceLevel.STANDARD,
        )
        tmp_thoughts.create(
            slug="critical-one",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            governance_level=GovernanceLevel.CRITICAL,
        )
        criticals = tmp_thoughts.manifest.get_by_governance(GovernanceLevel.CRITICAL)
        standards = tmp_thoughts.manifest.get_by_governance(GovernanceLevel.STANDARD)
        assert len(criticals) == 1
        assert len(standards) == 1
        assert "critical-one" in criticals[0]


# ---------------------------------------------------------------------------
# Remediation
# ---------------------------------------------------------------------------

class TestRemediation:
    def test_critical_thought_creates_flag(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="critical-decision",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            governance_level=GovernanceLevel.CRITICAL,
        )
        flag_dir = tmp_thoughts.dir.parent / "remediation" / "flags"
        flags = list(flag_dir.glob("*.flag"))
        assert len(flags) == 1

    def test_sovereign_thought_creates_flag(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="sovereign-decision",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            governance_level=GovernanceLevel.SOVEREIGN,
        )
        flag_dir = tmp_thoughts.dir.parent / "remediation" / "flags"
        flags = list(flag_dir.glob("*.flag"))
        assert len(flags) == 1

    def test_standard_thought_no_flag(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="standard-decision",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            governance_level=GovernanceLevel.STANDARD,
        )
        flag_dir = tmp_thoughts.dir.parent / "remediation" / "flags"
        assert not flag_dir.exists() or len(list(flag_dir.glob("*.flag"))) == 0

    def test_remediation_required_creates_flag(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="needs-attention",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            remediation_required=True,
        )
        flag_dir = tmp_thoughts.dir.parent / "remediation" / "flags"
        flags = list(flag_dir.glob("*.flag"))
        assert len(flags) == 1
        flag_data = json.loads(flags[0].read_text())
        assert flag_data["reason"] == "remediation_required"
        assert flag_data["status"] == "open"
        assert flag_data["resolved"] is False

    def test_resolve_flag(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="resolve-me",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            governance_level=GovernanceLevel.CRITICAL,
        )
        layer = RemediationLayer(
            tmp_thoughts.dir.parent / "remediation" / "flags"
        )
        flag = layer.resolve(
            thought_id="0001",
            resolution_note="Accepted risk. Tracked in 0005.",
            resolved_by="human",
        )
        assert flag.resolved is True
        assert flag.resolution_note == "Accepted risk. Tracked in 0005."

    def test_resolve_already_resolved_raises(self, tmp_thoughts: ThoughtWriter):
        tmp_thoughts.create(
            slug="already-resolved",
            author="human",
            stage_context="S",
            decision="D",
            reasoning="R",
            tags=[],
            governance_level=GovernanceLevel.CRITICAL,
        )
        layer = RemediationLayer(
            tmp_thoughts.dir.parent / "remediation" / "flags"
        )
        layer.resolve("0001", "First resolution.", "human")
        with pytest.raises(ValueError, match="already resolved"):
            layer.resolve("0001", "Trying again.", "human")

    def test_summary_counts(self, tmp_thoughts: ThoughtWriter):
        for slug in ["crit1", "crit2"]:
            tmp_thoughts.create(
                slug=slug,
                author="human",
                stage_context="S",
                decision="D",
                reasoning="R",
                tags=[],
                governance_level=GovernanceLevel.CRITICAL,
            )
        layer = RemediationLayer(
            tmp_thoughts.dir.parent / "remediation" / "flags"
        )
        summary = layer.summary()
        assert summary["total"] == 2
        assert summary["open"] == 2
        assert summary["open_critical"] == 2
        assert summary["needs_attention"] is True

        layer.resolve("0001", "Resolved.", "human")
        summary2 = layer.summary()
        assert summary2["open"] == 1
        assert summary2["resolved"] == 1
