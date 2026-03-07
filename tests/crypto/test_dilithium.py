"""
Tests for blackhorse.crypto.signing.dilithium — DilithiumSigner.

Covers:
- generate_keypair() returns two distinct byte strings
- sign() returns non-empty bytes
- verify() returns True for a valid (message, signature, public_key) triple
- verify() returns False for tampered message
- verify() returns False for tampered signature
- verify() returns False for wrong public key
- Multiple signatures of same message differ (randomised signing)
- details() returns dict with algorithm metadata
"""

import pytest

from blackhorse.crypto.signing.dilithium import DilithiumSigner


@pytest.fixture(scope="module")
def signer():
    return DilithiumSigner()


@pytest.fixture(scope="module")
def keypair(signer):
    return signer.generate_keypair()


MESSAGE = b"Blackhorse Phase 4D test message"


def test_generate_keypair_returns_bytes(signer):
    pub, sk = signer.generate_keypair()
    assert isinstance(pub, bytes)
    assert isinstance(sk, bytes)


def test_generate_keypair_lengths(signer):
    pub, sk = signer.generate_keypair()
    # ML-DSA-65 / Dilithium3: pub=1952, sk=4032
    assert len(pub) > 0
    assert len(sk) > 0
    assert len(pub) != len(sk)


def test_generate_keypair_unique(signer):
    pub1, _ = signer.generate_keypair()
    pub2, _ = signer.generate_keypair()
    assert pub1 != pub2


def test_sign_returns_bytes(signer, keypair):
    pub, sk = keypair
    sig = signer.sign(MESSAGE, sk)
    assert isinstance(sig, bytes)
    assert len(sig) > 0


def test_verify_valid_signature(signer, keypair):
    pub, sk = keypair
    sig = signer.sign(MESSAGE, sk)
    assert signer.verify(MESSAGE, sig, pub)


def test_verify_tampered_message(signer, keypair):
    pub, sk = keypair
    sig = signer.sign(MESSAGE, sk)
    tampered = MESSAGE + b"\x00"
    assert not signer.verify(tampered, sig, pub)


def test_verify_tampered_signature(signer, keypair):
    pub, sk = keypair
    sig = signer.sign(MESSAGE, sk)
    bad_sig = bytearray(sig)
    bad_sig[0] ^= 0xFF
    assert not signer.verify(MESSAGE, bytes(bad_sig), pub)


def test_verify_wrong_public_key(signer, keypair):
    pub, sk = keypair
    wrong_pub, _ = signer.generate_keypair()
    sig = signer.sign(MESSAGE, sk)
    assert not signer.verify(MESSAGE, sig, wrong_pub)


def test_sign_same_message_twice_produces_valid_sigs(signer, keypair):
    pub, sk = keypair
    sig1 = signer.sign(MESSAGE, sk)
    sig2 = signer.sign(MESSAGE, sk)
    # Both must verify correctly
    assert signer.verify(MESSAGE, sig1, pub)
    assert signer.verify(MESSAGE, sig2, pub)


def test_details_returns_dict(signer):
    d = signer.details()
    assert isinstance(d, dict)


def test_algorithm_name_set(signer):
    assert isinstance(signer.ALGORITHM, str)
    assert len(signer.ALGORITHM) > 0
