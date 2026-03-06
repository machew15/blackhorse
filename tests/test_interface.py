"""Tests for Stage 7 — Blackhorse AI Handshake Interface (full pipeline)."""

import time
import pytest

from blackhorse.interface import BlackhorseSession, BHPPacket, BHP_MAGIC
from blackhorse.interface.handshake import BHPError, HS_MAGIC


class TestBlackhorsePipeline:
    """End-to-end tests for the full .bhp pack/unpack pipeline."""

    def setup_method(self):
        # Sender and recipient share a signing key out-of-band.
        self.signing_key = BlackhorseSession().signing_key
        self.sender = BlackhorseSession(
            agent_info={"model": "test-agent", "version": "1.0"},
            signing_key=self.signing_key,
        )
        self.recipient = BlackhorseSession(signing_key=self.signing_key)

    def test_pack_produces_bytes(self):
        packet = self.sender.pack("Hello", self.recipient.public_key_bytes)
        assert isinstance(packet, bytes)

    def test_pack_unpack_round_trip(self):
        message = "Hello, sovereign world!"
        packet = self.sender.pack(message, self.recipient.public_key_bytes)
        recovered, meta = self.recipient.unpack(packet)
        assert recovered == message

    def test_empty_message(self):
        packet = self.sender.pack("", self.recipient.public_key_bytes)
        recovered, _ = self.recipient.unpack(packet)
        assert recovered == ""

    def test_unicode_message(self):
        message = "Blackhorse: 黑马协议 🐴"
        packet = self.sender.pack(message, self.recipient.public_key_bytes)
        recovered, _ = self.recipient.unpack(packet)
        assert recovered == message

    def test_long_message(self):
        message = "The quick brown fox jumps over the lazy dog. " * 200
        packet = self.sender.pack(message, self.recipient.public_key_bytes)
        recovered, _ = self.recipient.unpack(packet)
        assert recovered == message

    def test_metadata_contains_sender_pubkey(self):
        packet = self.sender.pack("test", self.recipient.public_key_bytes)
        _, meta = self.recipient.unpack(packet)
        assert "sender_pubkey" in meta
        assert isinstance(meta["sender_pubkey"], str)
        assert len(meta["sender_pubkey"]) == 64   # 32-byte hex string

    def test_metadata_contains_timestamp(self):
        before = int(time.time())
        packet = self.sender.pack("test", self.recipient.public_key_bytes)
        _, meta = self.recipient.unpack(packet)
        after = int(time.time())
        assert before <= meta["timestamp"] <= after + 1

    def test_packet_starts_with_bhp_magic(self):
        packet = self.sender.pack("test", self.recipient.public_key_bytes)
        assert packet[:4] == BHP_MAGIC

    def test_wrong_signing_key_raises(self):
        wrong_key = BlackhorseSession().signing_key
        packet = self.sender.pack("secret", self.recipient.public_key_bytes)
        with pytest.raises(BHPError):
            self.recipient.unpack(packet, signing_key=wrong_key)

    def test_tampered_packet_raises(self):
        packet = bytearray(
            self.sender.pack("important", self.recipient.public_key_bytes)
        )
        packet[70] ^= 0xFF   # flip a bit inside the payload
        with pytest.raises(BHPError):
            self.recipient.unpack(bytes(packet))

    def test_unpack_bytes_returns_bytes(self):
        data = b"\x00\xFF\xDE\xAD\xBE\xEF"
        packet = self.sender.pack(data, self.recipient.public_key_bytes)
        recovered, _ = self.recipient.unpack_bytes(packet)
        assert recovered == data

    def test_binary_data_round_trip(self):
        data = bytes(range(256))
        packet = self.sender.pack(data, self.recipient.public_key_bytes)
        recovered, _ = self.recipient.unpack_bytes(packet)
        assert recovered == data

    def test_each_pack_produces_different_ciphertext(self):
        """Ephemeral keys ensure no two packets are identical."""
        msg = "repeated message"
        p1 = self.sender.pack(msg, self.recipient.public_key_bytes)
        p2 = self.sender.pack(msg, self.recipient.public_key_bytes)
        assert p1 != p2

    def test_bhp_packet_parse(self):
        raw = self.sender.pack("test", self.recipient.public_key_bytes)
        pkt = BHPPacket.from_bytes(raw)
        assert len(pkt.sender_pubkey) == 32
        assert len(pkt.nonce) == 12

    def test_truncated_bhp_raises(self):
        with pytest.raises(BHPError):
            BHPPacket.from_bytes(b"\x00" * 10)

    def test_bad_bhp_magic_raises(self):
        raw = bytearray(self.sender.pack("test", self.recipient.public_key_bytes))
        raw[0] = 0xFF
        with pytest.raises(BHPError):
            BHPPacket.from_bytes(bytes(raw))


class TestHandshake:
    """Tests for the session handshake protocol."""

    def test_handshake_produces_bytes(self):
        session = BlackhorseSession(agent_info={"model": "test"})
        hs = session.handshake()
        assert isinstance(hs, bytes)

    def test_handshake_starts_with_magic(self):
        session = BlackhorseSession()
        hs = session.handshake()
        assert hs[:4] == HS_MAGIC

    def test_handshake_contains_pubkey(self):
        session = BlackhorseSession()
        hs = session.handshake()
        # public key is embedded at offset 8
        pubkey_in_hs = hs[8:40]
        assert pubkey_in_hs == session.public_key_bytes

    def test_from_handshake_round_trip(self):
        sender = BlackhorseSession(agent_info={"model": "sender-ai"})
        hs = sender.handshake()
        parsed = BlackhorseSession.from_handshake(hs)
        assert parsed._agent_info.get("_remote_pubkey") == sender.public_key_bytes.hex()

    def test_from_handshake_then_communicate(self):
        """After a handshake exchange, both sides can encrypt for each other."""
        signing_key = BlackhorseSession().signing_key

        alice = BlackhorseSession(signing_key=signing_key)
        bob = BlackhorseSession(signing_key=signing_key)

        # Alice sends Bob a packet.
        hs_alice = alice.handshake()
        # Bob learns Alice's public key from the handshake.
        alice_pubkey = hs_alice[8:40]

        packet = bob.pack("Hi Alice!", alice_pubkey, signing_key=signing_key)
        message, _ = alice.unpack(packet, signing_key=signing_key)
        assert message == "Hi Alice!"

    def test_from_handshake_bad_magic_raises(self):
        with pytest.raises(BHPError):
            BlackhorseSession.from_handshake(b"\xFF\xFF\xFF\xFF" + b"\x00" * 40)

    def test_agent_info_in_handshake(self):
        info = {"model": "claude-sonnet", "version": "4.6", "stage": 7}
        session = BlackhorseSession(agent_info=info)
        hs = session.handshake()
        # Parse and verify info is embedded
        parsed = BlackhorseSession.from_handshake(hs)
        assert parsed._agent_info.get("model") == "claude-sonnet"
        assert parsed._agent_info.get("version") == "4.6"

    def test_repr_is_informative(self):
        session = BlackhorseSession(agent_info={"model": "test"})
        r = repr(session)
        assert "BlackhorseSession" in r
        assert "pubkey" in r


class TestSessionProperties:
    def test_public_key_is_32_bytes(self):
        s = BlackhorseSession()
        assert len(s.public_key_bytes) == 32

    def test_signing_key_is_32_bytes(self):
        s = BlackhorseSession()
        assert len(s.signing_key) == 32

    def test_custom_signing_key(self):
        key = bytes(range(32))
        s = BlackhorseSession(signing_key=key)
        assert s.signing_key == key
