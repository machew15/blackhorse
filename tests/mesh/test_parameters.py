"""
Tests for blackhorse.mesh.parameters — PolicyConfig, ParticipationPolicy.

Covers:
- Default PolicyConfig values
- should_relay() APPROVED for compliant packet
- should_relay() rejected: queue full (flood gate)
- should_relay() rejected: packet too large
- should_relay() rejected: priority too low
- should_relay() rejected: rate limit exceeded
- should_relay() rejected: trust too low (known node)
- should_relay() approved: unknown node with relay_unknown_nodes=True
- should_relay() rejected: unknown node with relay_unknown_nodes=False
- record_relay() updates hourly count
- get_policy_report() returns dict with config and counts
"""

import pytest

from blackhorse.mesh.parameters import PolicyConfig, ParticipationPolicy
from blackhorse.mesh.ledger import ContributionLedger
from blackhorse.mesh.governance import ContributionIssuer
from blackhorse.crypto.signing.hmac_bhl import BHLSigner


SIGNING_KEY = BHLSigner.generate_key()
KNOWN_NODE = "k" * 64
UNKNOWN_NODE = "u" * 64


@pytest.fixture
def ledger(tmp_path):
    l = ContributionLedger(str(tmp_path / "ledger.db"))
    yield l
    l.close()


@pytest.fixture
def policy(ledger):
    config = PolicyConfig(
        max_bytes_per_relay=1000,
        max_relays_per_hour=5,
        max_queue_size=100,
        min_trust_score=0.5,
        relay_unknown_nodes=True,
        priority_threshold=1,
        bandwidth_reserve_pct=0.2,
    )
    return ParticipationPolicy(config=config, ledger=ledger)


# ---------------------------------------------------------------------------
# PolicyConfig defaults
# ---------------------------------------------------------------------------

def test_policy_config_defaults():
    cfg = PolicyConfig()
    assert cfg.max_bytes_per_relay == 1_048_576
    assert cfg.max_relays_per_hour == 100
    assert cfg.max_queue_size == 10_000
    assert cfg.min_trust_score == 0.0
    assert cfg.relay_unknown_nodes is True
    assert cfg.priority_threshold == 1
    assert cfg.bandwidth_reserve_pct == 0.2


def test_policy_config_to_dict():
    cfg = PolicyConfig()
    d = cfg.to_dict()
    assert "max_bytes_per_relay" in d
    assert "max_relays_per_hour" in d


# ---------------------------------------------------------------------------
# should_relay — approved
# ---------------------------------------------------------------------------

def test_should_relay_approved(policy):
    ok, reason = policy.should_relay(UNKNOWN_NODE, packet_size_bytes=100, priority=1)
    assert ok
    assert reason == "APPROVED"


# ---------------------------------------------------------------------------
# should_relay — rejected: packet too large
# ---------------------------------------------------------------------------

def test_should_relay_rejected_packet_too_large(policy):
    ok, reason = policy.should_relay(UNKNOWN_NODE, packet_size_bytes=10_000, priority=1)
    assert not ok
    assert "PACKET_TOO_LARGE" in reason


# ---------------------------------------------------------------------------
# should_relay — rejected: priority too low
# ---------------------------------------------------------------------------

def test_should_relay_rejected_priority_too_low(ledger):
    config = PolicyConfig(priority_threshold=2, max_bytes_per_relay=10_000)
    p = ParticipationPolicy(config=config, ledger=ledger)
    ok, reason = p.should_relay(UNKNOWN_NODE, packet_size_bytes=100, priority=1)
    assert not ok
    assert "PRIORITY_TOO_LOW" in reason


# ---------------------------------------------------------------------------
# should_relay — rejected: rate limit
# ---------------------------------------------------------------------------

def test_should_relay_rejected_rate_limited(ledger):
    config = PolicyConfig(max_relays_per_hour=2, max_bytes_per_relay=10_000)
    p = ParticipationPolicy(config=config, ledger=ledger)
    p.record_relay(UNKNOWN_NODE, 100)
    p.record_relay(UNKNOWN_NODE, 100)
    ok, reason = p.should_relay(UNKNOWN_NODE, 100, priority=1)
    assert not ok
    assert "RATE_LIMITED" in reason


# ---------------------------------------------------------------------------
# should_relay — unknown node
# ---------------------------------------------------------------------------

def test_should_relay_unknown_node_allowed_by_default(policy):
    ok, reason = policy.should_relay(UNKNOWN_NODE, 100, 1)
    assert ok


def test_should_relay_unknown_node_rejected_when_disabled(ledger):
    config = PolicyConfig(relay_unknown_nodes=False, max_bytes_per_relay=10_000)
    p = ParticipationPolicy(config=config, ledger=ledger)
    ok, reason = p.should_relay(UNKNOWN_NODE, 100, 1)
    assert not ok
    assert "UNKNOWN_NODE" in reason


# ---------------------------------------------------------------------------
# should_relay — trust score
# ---------------------------------------------------------------------------

def test_should_relay_rejected_low_trust(ledger):
    # Give KNOWN_NODE 0 verified contributions → trust_score = 0.0
    # But score of 0.0 triggers "unknown" branch, not trust branch,
    # unless node has unverified entries
    issuer = ContributionIssuer(node_id="origin", signing_key=SIGNING_KEY)
    receipt = issuer.issue(KNOWN_NODE, "msg1", b"\xAA" * 32)
    ledger.record(receipt, direction="GIVEN", verified=False)

    config = PolicyConfig(min_trust_score=0.5, relay_unknown_nodes=False, max_bytes_per_relay=10_000)
    p = ParticipationPolicy(config=config, ledger=ledger)
    ok, reason = p.should_relay(KNOWN_NODE, 100, 1)
    assert not ok


# ---------------------------------------------------------------------------
# Flood gate
# ---------------------------------------------------------------------------

def test_should_relay_rejected_queue_full(ledger, tmp_path):
    from blackhorse.mesh.queue import MessageQueue
    q = MessageQueue(str(tmp_path / "q.db"))
    config = PolicyConfig(max_queue_size=0, max_bytes_per_relay=10_000)
    p = ParticipationPolicy(config=config, ledger=ledger, queue=q)
    ok, reason = p.should_relay(UNKNOWN_NODE, 100, 1)
    assert not ok
    assert "QUEUE_FULL" in reason
    q.close()


# ---------------------------------------------------------------------------
# record_relay / get_policy_report
# ---------------------------------------------------------------------------

def test_record_relay_updates_counts(policy):
    policy.record_relay(UNKNOWN_NODE, 500)
    report = policy.get_policy_report()
    counts = report["hourly_relay_counts"]
    assert UNKNOWN_NODE in counts
    assert counts[UNKNOWN_NODE] == 1


def test_get_policy_report_has_config(policy):
    report = policy.get_policy_report()
    assert "config" in report
    assert "max_bytes_per_relay" in report["config"]
