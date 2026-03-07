"""
Tests for blackhorse.agents.attestation — DecisionAttestor.

Covers:
- attest() returns AgentDecisionPacket with correct fields
- agent_id is SHA-256 of signing key
- reasoning truncation at 500 chars
- verify() returns True for own packet
- verify() returns False for tampered packet
- verify() returns False for wrong key
- serialize / deserialize round-trip
- generate_key() produces 32 random bytes
"""

import hashlib
import json

import pytest

from blackhorse.agents.attestation import AgentDecisionPacket, DecisionAttestor


@pytest.fixture
def key():
    return DecisionAttestor.generate_key()


@pytest.fixture
def attestor(key):
    return DecisionAttestor(key)


INPUT = b"user query bytes"
OUTPUT = b"agent response bytes"
SCOPE = "scope-uuid-1234"


def test_attest_returns_decision_packet(attestor):
    packet = attestor.attest(INPUT, "Reasoning here.", OUTPUT, SCOPE)
    assert isinstance(packet, AgentDecisionPacket)


def test_attest_agent_id_is_sha256_of_key(key, attestor):
    expected = hashlib.sha256(key).hexdigest()
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    assert packet.agent_id == expected
    assert attestor.agent_id == expected


def test_attest_input_hash_correct(attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    assert packet.input_hash == hashlib.sha256(INPUT).hexdigest()


def test_attest_output_hash_correct(attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    assert packet.output_hash == hashlib.sha256(OUTPUT).hexdigest()


def test_attest_scope_ref_set(attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    assert packet.scope_ref == SCOPE


def test_attest_reasoning_truncated_at_500(attestor):
    long_reason = "x" * 600
    packet = attestor.attest(INPUT, long_reason, OUTPUT, SCOPE)
    assert len(packet.reasoning_summary) == 500


def test_attest_reasoning_short_unchanged(attestor):
    reason = "Short reason."
    packet = attestor.attest(INPUT, reason, OUTPUT, SCOPE)
    assert packet.reasoning_summary == reason


def test_attest_signature_non_empty(attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    assert len(packet.signature) == 32


def test_verify_returns_true_for_own_packet(key, attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    assert attestor.verify(packet, key)


def test_verify_returns_false_for_tampered_agent_id(key, attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    packet.agent_id = "tampered"
    assert not attestor.verify(packet, key)


def test_verify_returns_false_for_tampered_output_hash(key, attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    packet.output_hash = "tampered"
    assert not attestor.verify(packet, key)


def test_verify_returns_false_for_wrong_key(attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    wrong_key = DecisionAttestor.generate_key()
    assert not attestor.verify(packet, wrong_key)


def test_verify_returns_false_for_empty_signature(attestor):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    packet.signature = b""
    assert not attestor.verify(packet, DecisionAttestor.generate_key())


def test_serialize_deserialize_round_trip(attestor, key):
    packet = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    data = attestor.serialize(packet)
    restored = DecisionAttestor.deserialize(data)
    assert restored.agent_id == packet.agent_id
    assert restored.decision_id == packet.decision_id
    assert restored.input_hash == packet.input_hash
    assert restored.output_hash == packet.output_hash
    assert restored.signature == packet.signature
    assert attestor.verify(restored, key)


def test_decision_id_is_unique_per_attest(attestor):
    p1 = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    p2 = attestor.attest(INPUT, "r", OUTPUT, SCOPE)
    assert p1.decision_id != p2.decision_id


def test_wrong_key_size_raises():
    with pytest.raises(ValueError):
        DecisionAttestor(b"\x00" * 16)
