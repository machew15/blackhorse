"""Tests for Stage 5 — Curve25519 Asymmetric Key Exchange."""

import pytest

from blackhorse.crypto.asymmetric import Curve25519, KeyPair


class TestCurve25519:
    def test_generate_produces_keypair(self):
        kp = Curve25519.generate()
        assert isinstance(kp, KeyPair)
        assert len(kp.public_key_bytes) == 32

    def test_public_key_is_32_bytes(self):
        kp = Curve25519.generate()
        assert len(kp.public_key_bytes) == 32

    def test_private_key_bytes_are_32_bytes(self):
        kp = Curve25519.generate()
        assert len(kp.private_key_bytes()) == 32

    def test_two_keypairs_differ(self):
        kp1 = Curve25519.generate()
        kp2 = Curve25519.generate()
        assert kp1.public_key_bytes != kp2.public_key_bytes

    def test_ecdh_shared_secret_matches(self):
        alice = Curve25519.generate()
        bob = Curve25519.generate()
        shared_alice = Curve25519.exchange(alice, bob.public_key_bytes)
        shared_bob = Curve25519.exchange(bob, alice.public_key_bytes)
        assert shared_alice == shared_bob

    def test_shared_secret_is_32_bytes(self):
        alice = Curve25519.generate()
        bob = Curve25519.generate()
        secret = Curve25519.exchange(alice, bob.public_key_bytes)
        assert len(secret) == 32

    def test_different_peers_different_secrets(self):
        alice = Curve25519.generate()
        bob = Curve25519.generate()
        charlie = Curve25519.generate()
        s_ab = Curve25519.exchange(alice, bob.public_key_bytes)
        s_ac = Curve25519.exchange(alice, charlie.public_key_bytes)
        assert s_ab != s_ac

    def test_info_parameter_changes_derived_key(self):
        alice = Curve25519.generate()
        bob = Curve25519.generate()
        k1 = Curve25519.exchange(alice, bob.public_key_bytes, info=b"context-1")
        k2 = Curve25519.exchange(alice, bob.public_key_bytes, info=b"context-2")
        assert k1 != k2

    def test_salt_parameter_changes_derived_key(self):
        alice = Curve25519.generate()
        bob = Curve25519.generate()
        s1 = Curve25519.generate_salt()
        s2 = Curve25519.generate_salt()
        k1 = Curve25519.exchange(alice, bob.public_key_bytes, salt=s1)
        k2 = Curve25519.exchange(alice, bob.public_key_bytes, salt=s2)
        assert k1 != k2

    def test_salt_consistent_with_same_salt(self):
        alice = Curve25519.generate()
        bob = Curve25519.generate()
        salt = Curve25519.generate_salt()
        k1 = Curve25519.exchange(alice, bob.public_key_bytes, salt=salt)
        k2 = Curve25519.exchange(alice, bob.public_key_bytes, salt=salt)
        assert k1 == k2

    def test_from_private_bytes_round_trip(self):
        kp = Curve25519.generate()
        raw_priv = kp.private_key_bytes()
        kp2 = Curve25519.from_private_bytes(raw_priv)
        assert kp2.public_key_bytes == kp.public_key_bytes

    def test_bad_peer_pubkey_length_raises(self):
        kp = Curve25519.generate()
        with pytest.raises(ValueError):
            Curve25519.exchange(kp, b"too_short")

    def test_generate_salt_is_32_bytes(self):
        salt = Curve25519.generate_salt()
        assert len(salt) == 32

    def test_generate_salt_is_random(self):
        s1 = Curve25519.generate_salt()
        s2 = Curve25519.generate_salt()
        assert s1 != s2
