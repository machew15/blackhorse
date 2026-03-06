"""Tests for Stage 2 — Blackhorse Language (BHL)."""

import pytest

from blackhorse.language import BHLEncoder, BHLDecoder, BHLPacket, BHL_MAGIC
from blackhorse.language.symbols import (
    TABLE_0_ORDER,
    TABLE_0_ENCODE,
    code_for_position,
    average_bits_per_byte,
    get_table,
)
from blackhorse.language.packet import BHLError


# ---------------------------------------------------------------------------
# Symbol table tests
# ---------------------------------------------------------------------------

class TestSymbols:
    def test_table_covers_all_256_bytes(self):
        assert len(TABLE_0_ORDER) == 256
        assert set(TABLE_0_ORDER) == set(range(256))

    def test_encode_map_is_inverse(self):
        for i, byte_val in enumerate(TABLE_0_ORDER):
            assert TABLE_0_ENCODE[byte_val] == i

    def test_code_lengths_are_7_8_or_9(self):
        for pos in range(256):
            _, length = code_for_position(pos)
            assert length in (7, 8, 9), f"pos {pos} has length {length}"

    def test_group_a_is_7_bit(self):
        for pos in range(64):
            _, length = code_for_position(pos)
            assert length == 7

    def test_group_b_is_8_bit(self):
        for pos in range(64, 128):
            _, length = code_for_position(pos)
            assert length == 8

    def test_group_c_is_9_bit(self):
        for pos in range(128, 256):
            _, length = code_for_position(pos)
            assert length == 9

    def test_codes_are_prefix_free(self):
        """No code should be a prefix of any other code."""
        for p1 in range(256):
            code1, len1 = code_for_position(p1)
            bits1 = format(code1, f"0{len1}b")
            for p2 in range(256):
                if p1 == p2:
                    continue
                code2, len2 = code_for_position(p2)
                bits2 = format(code2, f"0{len2}b")
                shorter = bits1 if len1 <= len2 else bits2
                longer = bits2 if len1 <= len2 else bits1
                assert not longer.startswith(shorter) or shorter == longer, \
                    f"Code {p1} ({bits1}) is prefix of code {p2} ({bits2})"

    def test_space_gets_7bit_code(self):
        pos = TABLE_0_ENCODE[0x20]
        assert pos < 64

    def test_average_bits_under_9(self):
        avg = average_bits_per_byte(0)
        assert avg < 9.0

    def test_get_table_unknown_raises(self):
        with pytest.raises(KeyError):
            get_table(99)


# ---------------------------------------------------------------------------
# BHLPacket tests
# ---------------------------------------------------------------------------

class TestBHLPacket:
    def test_round_trip_empty_payload(self):
        p = BHLPacket.build(b"", bit_count=0)
        wire = p.to_bytes()
        p2 = BHLPacket.from_bytes(wire)
        assert p2.bit_count == 0
        assert p2.payload == b""

    def test_round_trip_with_payload(self):
        payload = b"\xAB\xCD\xEF"
        p = BHLPacket.build(payload, bit_count=24)
        wire = p.to_bytes()
        p2 = BHLPacket.from_bytes(wire)
        assert p2.payload == payload
        assert p2.bit_count == 24

    def test_magic_in_wire_bytes(self):
        p = BHLPacket.build(b"\x00", bit_count=8)
        wire = p.to_bytes()
        assert wire[:4] == BHL_MAGIC

    def test_bad_magic_raises(self):
        p = BHLPacket.build(b"\x00", bit_count=8)
        wire = bytearray(p.to_bytes())
        wire[0] = 0xFF
        with pytest.raises(BHLError):
            BHLPacket.from_bytes(bytes(wire))

    def test_bad_crc_raises(self):
        p = BHLPacket.build(b"\xAA", bit_count=8)
        wire = bytearray(p.to_bytes())
        wire[-1] ^= 0xFF   # corrupt CRC
        with pytest.raises(BHLError):
            BHLPacket.from_bytes(bytes(wire))

    def test_truncated_raises(self):
        with pytest.raises(BHLError):
            BHLPacket.from_bytes(b"\x00" * 5)


# ---------------------------------------------------------------------------
# BHLEncoder / BHLDecoder round-trip tests
# ---------------------------------------------------------------------------

class TestEncoderDecoder:
    @pytest.fixture
    def encoder(self):
        return BHLEncoder()

    @pytest.fixture
    def decoder(self):
        return BHLDecoder()

    def test_ascii_round_trip(self, encoder, decoder):
        text = "Hello, sovereign world!"
        assert decoder.decode(encoder.encode(text)) == text

    def test_empty_string(self, encoder, decoder):
        assert decoder.decode(encoder.encode("")) == ""

    def test_all_ascii_printable(self, encoder, decoder):
        text = "".join(chr(c) for c in range(32, 127))
        assert decoder.decode(encoder.encode(text)) == text

    def test_unicode_text(self, encoder, decoder):
        text = "Sovereign AI: 主权人工智能 🐴"
        assert decoder.decode(encoder.encode(text)) == text

    def test_encode_bytes_round_trip(self, encoder, decoder):
        data = bytes(range(256))
        assert decoder.decode_bytes(encoder.encode_bytes(data)) == data

    def test_binary_data_round_trip(self, encoder, decoder):
        data = bytes([i % 256 for i in range(512)])
        assert decoder.decode_bytes(encoder.encode_bytes(data)) == data

    def test_long_text(self, encoder, decoder):
        text = "The quick brown fox jumps over the lazy dog. " * 100
        assert decoder.decode(encoder.encode(text)) == text

    def test_packet_is_bytes(self, encoder):
        result = encoder.encode("test")
        assert isinstance(result, bytes)

    def test_encode_decode_newlines(self, encoder, decoder):
        text = "line1\nline2\nline3\n"
        assert decoder.decode(encoder.encode(text)) == text

    def test_encode_decode_tab(self, encoder, decoder):
        text = "col1\tcol2\tcol3"
        assert decoder.decode(encoder.encode(text)) == text

    def test_common_text_shorter_than_uncommon(self, encoder):
        """BHL should encode common ASCII text more compactly than rare bytes."""
        common_text = "the quick brown fox"
        rare_bytes = bytes([0xE0 + i for i in range(len(common_text))])
        common_encoded = encoder.encode_bytes(common_text.encode())
        rare_encoded = encoder.encode_bytes(rare_bytes)
        assert len(common_encoded) < len(rare_encoded)

    def test_custom_encoding_param(self, encoder, decoder):
        text = "Hello"
        enc = encoder.encode(text, encoding="ascii")
        dec = decoder.decode(enc, encoding="ascii")
        assert dec == text
