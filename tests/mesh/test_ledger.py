"""
Tests for blackhorse.mesh.ledger — ContributionLedger, trust score.

Covers:
- record() stores contribution
- get_node_contributions() returns correct counts and bytes
- get_trust_score() returns 0.0 for unknown node
- get_trust_score() base calculation
- get_trust_score() capped at 1.0
- top_contributors() returns correct ranking
- export_report() returns non-empty string
"""

import pytest
from datetime import datetime, timezone, timedelta

from blackhorse.mesh.governance import ContributionReceipt, ContributionIssuer
from blackhorse.mesh.ledger import ContributionLedger
from blackhorse.crypto.signing.hmac_bhl import BHLSigner


NODE_A = "a" * 64
NODE_B = "b" * 64
SIGNING_KEY = BHLSigner.generate_key()


def _make_receipt(
    relay_node_id: str,
    origin_node_id: str,
    msg_id: str = "msg-1",
    packet: bytes = b"\xAA" * 32,
    ts: datetime | None = None,
) -> ContributionReceipt:
    issuer = ContributionIssuer(node_id=origin_node_id, signing_key=SIGNING_KEY)
    receipt = issuer.issue(relay_node_id, msg_id, packet)
    if ts is not None:
        receipt.relay_timestamp = ts
    return receipt


@pytest.fixture
def ledger(tmp_path):
    l = ContributionLedger(str(tmp_path / "ledger.db"))
    yield l
    l.close()


# ---------------------------------------------------------------------------
# record / get_node_contributions
# ---------------------------------------------------------------------------

def test_record_stores_contribution(ledger):
    receipt = _make_receipt(NODE_A, NODE_B)
    ledger.record(receipt, direction="GIVEN")
    summary = ledger.get_node_contributions(NODE_A)
    assert summary["given"] == 1


def test_record_invalid_direction_raises(ledger):
    receipt = _make_receipt(NODE_A, NODE_B)
    with pytest.raises(ValueError):
        ledger.record(receipt, direction="INVALID")


def test_get_node_contributions_given_and_received(ledger):
    # NODE_A gives a relay
    r1 = _make_receipt(NODE_A, NODE_B, msg_id="m1")
    ledger.record(r1, direction="GIVEN")
    # NODE_A receives a relay (as origin)
    r2 = _make_receipt(NODE_B, NODE_A, msg_id="m2")
    ledger.record(r2, direction="RECEIVED")
    summary = ledger.get_node_contributions(NODE_A)
    assert summary["given"] == 1
    assert summary["received"] == 1


def test_get_node_contributions_bytes(ledger):
    packet = b"\xBB" * 100
    receipt = _make_receipt(NODE_A, NODE_B, packet=packet)
    ledger.record(receipt, direction="GIVEN")
    summary = ledger.get_node_contributions(NODE_A)
    assert summary["bytes_given"] == 100


def test_get_node_contributions_unknown_node(ledger):
    summary = ledger.get_node_contributions("unknown")
    assert summary["given"] == 0
    assert summary["received"] == 0


# ---------------------------------------------------------------------------
# get_trust_score
# ---------------------------------------------------------------------------

def test_trust_score_unknown_node_is_zero(ledger):
    assert ledger.get_trust_score("nobody") == 0.0


def test_trust_score_all_verified_is_one(ledger):
    for i in range(5):
        receipt = _make_receipt(NODE_A, NODE_B, msg_id=f"m{i}")
        ledger.record(receipt, direction="GIVEN", verified=True)
    score = ledger.get_trust_score(NODE_A)
    assert score == pytest.approx(1.0, abs=0.01)


def test_trust_score_none_verified_is_zero(ledger):
    for i in range(5):
        receipt = _make_receipt(NODE_A, NODE_B, msg_id=f"m{i}")
        ledger.record(receipt, direction="GIVEN", verified=False)
    score = ledger.get_trust_score(NODE_A)
    assert score == pytest.approx(0.0, abs=0.01)


def test_trust_score_capped_at_one(ledger):
    # Many recent verified contributions should not exceed 1.0
    for i in range(20):
        receipt = _make_receipt(NODE_A, NODE_B, msg_id=f"m{i}")
        ledger.record(receipt, direction="GIVEN", verified=True)
    score = ledger.get_trust_score(NODE_A)
    assert score <= 1.0


def test_trust_score_half_verified(ledger):
    for i in range(10):
        receipt = _make_receipt(NODE_A, NODE_B, msg_id=f"m{i}")
        ledger.record(receipt, direction="GIVEN", verified=(i < 5))
    score = ledger.get_trust_score(NODE_A)
    assert 0.0 < score < 1.0


# ---------------------------------------------------------------------------
# top_contributors
# ---------------------------------------------------------------------------

def test_top_contributors_ranking(ledger):
    # NODE_A: 3 relays; NODE_B: 1 relay
    for i in range(3):
        r = _make_receipt(NODE_A, "origin", msg_id=f"a{i}")
        ledger.record(r, direction="GIVEN")
    r = _make_receipt(NODE_B, "origin", msg_id="b0")
    ledger.record(r, direction="GIVEN")

    top = ledger.top_contributors(limit=10)
    assert top[0]["node_id"] == NODE_A
    assert top[0]["given"] == 3
    assert top[1]["node_id"] == NODE_B


def test_top_contributors_empty_ledger(ledger):
    assert ledger.top_contributors() == []


def test_top_contributors_limit_respected(ledger):
    for i in range(5):
        nid = f"node_{i}" * 6  # make it 64 chars-ish
        r = _make_receipt(nid, "origin", msg_id=f"m{i}")
        ledger.record(r, direction="GIVEN")
    top = ledger.top_contributors(limit=3)
    assert len(top) <= 3


# ---------------------------------------------------------------------------
# export_report
# ---------------------------------------------------------------------------

def test_export_report_returns_string(ledger):
    report = ledger.export_report()
    assert isinstance(report, str)
    assert len(report) > 0


def test_export_report_contains_header(ledger):
    report = ledger.export_report()
    assert "BLACKHORSE" in report
    assert "CONTRIBUTION" in report
