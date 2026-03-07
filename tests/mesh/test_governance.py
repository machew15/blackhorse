"""
Tests for blackhorse.mesh.governance — ContributionReceipt, ContributionIssuer.

Covers:
- issue() creates a signed ContributionReceipt
- verify() returns True for valid receipt
- verify() returns False for tampered receipt
- verify() returns False for wrong signing key
- serialize() / deserialize() round-trip
- packet_hash is SHA-256 of packet_bytes
- receipt_id is unique per issue()
"""

import hashlib
import json
import pytest

from blackhorse.mesh.governance import ContributionReceipt, ContributionIssuer
from blackhorse.crypto.signing.hmac_bhl import BHLSigner


NODE_ID = "a" * 64
RELAY_ID = "b" * 64
SIGNING_KEY = BHLSigner.generate_key()
PACKET = b"\xBE\xEF" * 32
MSG_ID = "msg-uuid-1234"


@pytest.fixture
def issuer():
    return ContributionIssuer(node_id=NODE_ID, signing_key=SIGNING_KEY)


# ---------------------------------------------------------------------------
# issue()
# ---------------------------------------------------------------------------

def test_issue_returns_receipt(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    assert isinstance(receipt, ContributionReceipt)


def test_issue_packet_hash_is_sha256(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    expected = hashlib.sha256(PACKET).hexdigest()
    assert receipt.packet_hash == expected


def test_issue_bytes_relayed_correct(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    assert receipt.bytes_relayed == len(PACKET)


def test_issue_relay_node_id_set(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    assert receipt.relay_node_id == RELAY_ID


def test_issue_origin_node_id_is_issuer(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    assert receipt.origin_node_id == NODE_ID


def test_issue_signature_non_empty(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    assert len(receipt.signature) == 32


def test_issue_unique_receipt_id(issuer):
    r1 = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    r2 = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    assert r1.receipt_id != r2.receipt_id


def test_issue_custom_location(issuer):
    loc = '{"type":"Point","coordinates":[-0.1,51.5]}'
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET, relay_location=loc)
    assert receipt.spatial_context == loc


# ---------------------------------------------------------------------------
# verify()
# ---------------------------------------------------------------------------

def test_verify_valid_receipt(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    assert issuer.verify(receipt, SIGNING_KEY)


def test_verify_tampered_message_id(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    receipt.message_id = "tampered"
    assert not issuer.verify(receipt, SIGNING_KEY)


def test_verify_tampered_packet_hash(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    receipt.packet_hash = "a" * 64
    assert not issuer.verify(receipt, SIGNING_KEY)


def test_verify_wrong_key(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    wrong_key = BHLSigner.generate_key()
    assert not issuer.verify(receipt, wrong_key)


def test_verify_empty_signature(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    receipt.signature = b""
    assert not issuer.verify(receipt, SIGNING_KEY)


# ---------------------------------------------------------------------------
# serialize / deserialize
# ---------------------------------------------------------------------------

def test_serialize_returns_bytes(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    data = issuer.serialize(receipt)
    assert isinstance(data, bytes)
    assert len(data) > 0


def test_serialize_deserialize_round_trip(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    packed = issuer.serialize(receipt)
    restored = issuer.deserialize(packed, SIGNING_KEY)
    assert restored.receipt_id == receipt.receipt_id
    assert restored.message_id == receipt.message_id
    assert restored.packet_hash == receipt.packet_hash
    assert restored.bytes_relayed == receipt.bytes_relayed
    assert restored.signature == receipt.signature


def test_to_dict_from_dict_round_trip(issuer):
    receipt = issuer.issue(RELAY_ID, MSG_ID, PACKET)
    d = receipt.to_dict()
    restored = ContributionReceipt.from_dict(d)
    assert restored.receipt_id == receipt.receipt_id
    assert restored.signature == receipt.signature
