"""Tests for Stage 6 — HMAC-SHA256 + BHL Signing."""

import pytest

from blackhorse.crypto.signing import BHLSigner, SignedPacket
from blackhorse.crypto.signing.hmac_bhl import SigningError, SIGN_MAGIC


class TestBHLSigner:
    def setup_method(self):
        self.signer = BHLSigner()
        self.key = BHLSigner.generate_key()

    def test_sign_produces_bytes(self):
        signed = self.signer.sign(b"hello", self.key)
        assert isinstance(signed, bytes)

    def test_verify_valid_signature(self):
        payload = b"sovereign data"
        signed = self.signer.sign(payload, self.key)
        assert self.signer.verify(signed, self.key)

    def test_verify_and_extract_returns_payload(self):
        payload = b"original payload"
        signed = self.signer.sign(payload, self.key)
        recovered = self.signer.verify_and_extract(signed, self.key)
        assert recovered == payload

    def test_wrong_key_fails_verification(self):
        signed = self.signer.sign(b"data", self.key)
        wrong_key = BHLSigner.generate_key()
        assert not self.signer.verify(signed, wrong_key)

    def test_tampered_payload_fails_verification(self):
        payload = b"authentic data"
        signed = bytearray(self.signer.sign(payload, self.key))
        # Flip a bit in the payload region (after the 8-byte header)
        signed[8] ^= 0x01
        assert not self.signer.verify(bytes(signed), self.key)

    def test_tampered_tag_fails_verification(self):
        payload = b"authentic data"
        signed = bytearray(self.signer.sign(payload, self.key))
        signed[-1] ^= 0xFF   # corrupt last byte of HMAC tag
        assert not self.signer.verify(bytes(signed), self.key)

    def test_magic_present_in_wire_bytes(self):
        signed = self.signer.sign(b"test", self.key)
        assert signed[:4] == SIGN_MAGIC

    def test_empty_payload(self):
        signed = self.signer.sign(b"", self.key)
        recovered = self.signer.verify_and_extract(signed, self.key)
        assert recovered == b""

    def test_large_payload_round_trip(self):
        payload = bytes(range(256)) * 100
        signed = self.signer.sign(payload, self.key)
        assert self.signer.verify_and_extract(signed, self.key) == payload

    def test_verify_and_extract_raises_on_bad_hmac(self):
        signed = bytearray(self.signer.sign(b"data", self.key))
        signed[-1] ^= 0xFF
        with pytest.raises(SigningError):
            self.signer.verify_and_extract(bytes(signed), self.key)

    def test_generate_key_is_32_bytes(self):
        key = BHLSigner.generate_key()
        assert len(key) == 32

    def test_generate_key_is_random(self):
        k1 = BHLSigner.generate_key()
        k2 = BHLSigner.generate_key()
        assert k1 != k2

    def test_signed_packet_from_bytes_round_trip(self):
        payload = b"round trip test"
        signed = self.signer.sign(payload, self.key)
        packet = SignedPacket.from_bytes(signed)
        assert packet.payload == payload
        assert len(packet.tag) == 32

    def test_short_packet_raises(self):
        with pytest.raises(SigningError):
            SignedPacket.from_bytes(b"\x00" * 4)

    def test_bad_magic_raises(self):
        signed = bytearray(self.signer.sign(b"data", self.key))
        signed[0] = 0xFF
        with pytest.raises(SigningError):
            SignedPacket.from_bytes(bytes(signed))
