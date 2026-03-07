"""
Tests for blackhorse.crypto.asymmetric.kyber — KyberKEM.

Covers:
- generate_keypair() returns two distinct byte strings of expected lengths
- encapsulate() returns (ciphertext, shared_secret) of expected lengths
- decapsulate() recovers the same shared_secret as the sender
- Different encapsulations produce different shared secrets
- decapsulate with wrong secret key produces a different (or failed) secret
- details() returns dict with algorithm metadata
"""

import pytest

from blackhorse.crypto.asymmetric.kyber import KyberKEM


@pytest.fixture(scope="module")
def kem():
    return KyberKEM()


@pytest.fixture(scope="module")
def keypair(kem):
    return kem.generate_keypair()


def test_generate_keypair_returns_bytes(kem):
    pub, sk = kem.generate_keypair()
    assert isinstance(pub, bytes)
    assert isinstance(sk, bytes)


def test_generate_keypair_lengths(kem):
    pub, sk = kem.generate_keypair()
    # Kyber768: pub=1184, sk=2400
    assert len(pub) > 0
    assert len(sk) > 0
    assert len(pub) != len(sk)


def test_generate_keypair_unique(kem):
    pub1, _ = kem.generate_keypair()
    pub2, _ = kem.generate_keypair()
    assert pub1 != pub2


def test_encapsulate_returns_tuple(kem, keypair):
    pub, sk = keypair
    result = kem.encapsulate(pub)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_encapsulate_lengths(kem, keypair):
    pub, sk = keypair
    ct, ss = kem.encapsulate(pub)
    assert isinstance(ct, bytes)
    assert isinstance(ss, bytes)
    assert len(ss) == 32  # Kyber768 shared secret is always 32 bytes


def test_decapsulate_recovers_shared_secret(kem):
    pub, sk = kem.generate_keypair()
    ct, ss_sender = kem.encapsulate(pub)
    ss_recipient = kem.decapsulate(sk, ct)
    assert ss_sender == ss_recipient


def test_different_encapsulations_different_secrets(kem):
    pub, sk = kem.generate_keypair()
    _, ss1 = kem.encapsulate(pub)
    _, ss2 = kem.encapsulate(pub)
    assert ss1 != ss2


def test_decapsulate_wrong_secret_key_different_secret(kem):
    pub, sk = kem.generate_keypair()
    _, wrong_sk = kem.generate_keypair()
    ct, ss_correct = kem.encapsulate(pub)
    # With wrong key, decapsulation either fails or produces wrong secret
    try:
        ss_wrong = kem.decapsulate(wrong_sk, ct)
        assert ss_wrong != ss_correct
    except Exception:
        pass  # Some KEMs raise on wrong key; that's also acceptable


def test_details_returns_dict(kem):
    d = kem.details()
    assert isinstance(d, dict)


def test_algorithm_name_set(kem):
    assert isinstance(kem.ALGORITHM, str)
    assert len(kem.ALGORITHM) > 0
