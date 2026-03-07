"""
Tests for BlackhorseSession delivery receipt (Phase 1D).

Covers:
- generate_receipt + verify_receipt round-trip
- verify_receipt raises SigningError on tampered receipt
- verify_receipt raises SigningError on wrong signing key
- ReceiptPayload fields are correctly populated
"""

import pytest

from blackhorse.interface.handshake import BlackhorseSession, ReceiptPayload
from blackhorse.crypto.signing.hmac_bhl import SigningError, BHLSigner


@pytest.fixture
def session():
    return BlackhorseSession()


@pytest.fixture
def signing_key():
    return BHLSigner.generate_key()


def test_receipt_round_trip(session, signing_key):
    message_id = "test-message-uuid-1234"
    receipt = session.generate_receipt(message_id, signing_key)
    assert isinstance(receipt, bytes)
    assert len(receipt) > 0

    payload = session.verify_receipt(receipt, signing_key)
    assert isinstance(payload, ReceiptPayload)
    assert payload.message_id == message_id
    assert isinstance(payload.relay_node_id, str)
    assert len(payload.relay_node_id) > 0


def test_receipt_payload_timestamp_is_utc(session, signing_key):
    from datetime import timezone
    payload = session.verify_receipt(
        session.generate_receipt("msg-id", signing_key), signing_key
    )
    assert payload.timestamp.tzinfo is not None


def test_receipt_verify_raises_on_tampered_bytes(session, signing_key):
    receipt = session.generate_receipt("some-id", signing_key)
    tampered = bytearray(receipt)
    tampered[-5] ^= 0xFF  # flip bits in the HMAC tag
    with pytest.raises(SigningError):
        session.verify_receipt(bytes(tampered), signing_key)


def test_receipt_verify_raises_on_wrong_key(session, signing_key):
    receipt = session.generate_receipt("some-id", signing_key)
    wrong_key = BHLSigner.generate_key()
    with pytest.raises(SigningError):
        session.verify_receipt(receipt, wrong_key)


def test_receipt_relay_node_id_is_session_derived(signing_key):
    s1 = BlackhorseSession()
    s2 = BlackhorseSession()
    p1 = s1.verify_receipt(s1.generate_receipt("id", signing_key), signing_key)
    p2 = s2.verify_receipt(s2.generate_receipt("id", signing_key), signing_key)
    assert p1.relay_node_id != p2.relay_node_id
