"""Tests for Stage 1 — Blackhorse Core Library."""

import pytest

from blackhorse.core import BitStream, RingBuffer, crc32, xor_bytes
from blackhorse.core.utils import (
    pack_u32_be,
    unpack_u32_be,
    pack_u16_be,
    unpack_u16_be,
    bytes_to_bits_str,
    bits_str_to_bytes,
)


# ---------------------------------------------------------------------------
# BitStream tests
# ---------------------------------------------------------------------------

class TestBitStream:
    def test_write_and_read_single_bits(self):
        bs = BitStream()
        for bit in [1, 0, 1, 1, 0, 0, 1, 0]:
            bs.write_bit(bit)
        bs.rewind()
        result = [bs.read_bit() for _ in range(8)]
        assert result == [1, 0, 1, 1, 0, 0, 1, 0]

    def test_write_bits_msb_first(self):
        bs = BitStream()
        bs.write_bits(0b10110010, 8)
        bs.rewind()
        assert bs.read_byte() == 0b10110010

    def test_write_byte_round_trip(self):
        bs = BitStream()
        for val in [0x00, 0xFF, 0xA5, 0x42]:
            bs.write_byte(val)
        bs.rewind()
        for expected in [0x00, 0xFF, 0xA5, 0x42]:
            assert bs.read_byte() == expected

    def test_write_bytes_round_trip(self):
        data = bytes(range(16))
        bs = BitStream()
        bs.write_bytes(data)
        bs.rewind()
        result = bs.read_bytes(16)
        assert result == data

    def test_read_bits_arbitrary_width(self):
        bs = BitStream()
        bs.write_bits(0b101, 3)
        bs.write_bits(0b1100, 4)
        bs.rewind()
        assert bs.read_bits(3) == 0b101
        assert bs.read_bits(4) == 0b1100

    def test_eof_raises(self):
        bs = BitStream()
        bs.write_bit(1)
        bs.rewind()
        bs.read_bit()
        with pytest.raises(EOFError):
            bs.read_bit()

    def test_seek_read(self):
        bs = BitStream()
        bs.write_bits(0xFF, 8)
        bs.seek_read(4)
        assert bs.read_bits(4) == 0x0F

    def test_to_bytes_and_from_bytes(self):
        original = b"\xDE\xAD\xBE\xEF"
        bs = BitStream(original)
        assert bs.to_bytes() == original

    def test_bit_length(self):
        bs = BitStream()
        bs.write_bits(0, 13)
        assert bs.bit_length == 13

    def test_bits_remaining(self):
        bs = BitStream()
        bs.write_bits(0, 16)
        bs.rewind()
        bs.read_bits(7)
        assert bs.bits_remaining == 9

    def test_from_bytes_read_pos_is_zero(self):
        bs = BitStream.from_bytes(b"\xA5")
        assert bs.read_byte() == 0xA5

    def test_write_bit_zero_clears(self):
        bs = BitStream(b"\xFF")
        # From-bytes starts write pos at byte boundary; overwrite is not the
        # intended use — test that freshly written 0 bits are actually 0.
        bs2 = BitStream()
        bs2.write_bit(0)
        bs2.write_bit(0)
        bs2.write_bit(0)
        bs2.write_bit(0)
        bs2.rewind()
        assert bs2.read_bits(4) == 0


# ---------------------------------------------------------------------------
# RingBuffer tests
# ---------------------------------------------------------------------------

class TestRingBuffer:
    def test_push_and_read(self):
        rb = RingBuffer(8)
        rb.push(b"ABCD")
        assert rb.read(0, 4) == b"ABCD"

    def test_size_tracks_correctly(self):
        rb = RingBuffer(4)
        assert rb.size == 0
        rb.push(b"AB")
        assert rb.size == 2
        rb.push(b"CDXY")   # overflows by 2
        assert rb.size == 4

    def test_overwrite_oldest(self):
        rb = RingBuffer(4)
        rb.push(b"ABCD")
        rb.push(b"EF")   # overwrites A and B
        assert rb.read(0, 4) == b"CDEF"

    def test_find_match_exact(self):
        rb = RingBuffer(64)
        rb.push(b"hello world ")
        offset, length = rb.find_match(b"hello")
        assert length == 5
        assert offset > 0

    def test_find_match_no_match(self):
        rb = RingBuffer(64)
        rb.push(b"AAAA")
        offset, length = rb.find_match(b"ZZZZ")
        assert offset == 0
        assert length == 0

    def test_find_match_min_len_respected(self):
        rb = RingBuffer(64)
        rb.push(b"AB")
        offset, length = rb.find_match(b"AB", min_len=3)
        assert length == 0  # match exists but shorter than min_len

    def test_getitem(self):
        rb = RingBuffer(8)
        rb.push(b"XY")
        assert rb[0] == ord("X")
        assert rb[1] == ord("Y")
        assert rb[-1] == ord("Y")

    def test_getitem_out_of_range(self):
        rb = RingBuffer(4)
        rb.push(b"A")
        with pytest.raises(IndexError):
            _ = rb[5]

    def test_peek(self):
        rb = RingBuffer(8)
        rb.push(b"HELLO")
        assert rb.peek(3) == b"LLO"

    def test_capacity_enforcement(self):
        rb = RingBuffer(3)
        rb.push(b"ABCDEF")
        assert len(rb) == 3
        assert rb.peek() == b"DEF"

    def test_read_exceeds_raises(self):
        rb = RingBuffer(8)
        rb.push(b"AB")
        with pytest.raises(IndexError):
            rb.read(0, 5)


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------

class TestUtils:
    def test_crc32_known_value(self):
        assert crc32(b"") == 0x00000000
        assert crc32(b"123456789") == 0xCBF43926

    def test_crc32_consistency(self):
        data = b"blackhorse protocol"
        assert crc32(data) == crc32(data)

    def test_xor_bytes(self):
        assert xor_bytes(b"\xFF\x00", b"\x0F\xF0") == b"\xF0\xF0"
        assert xor_bytes(b"A", b"A") == b"\x00"

    def test_xor_bytes_unequal_raises(self):
        with pytest.raises(ValueError):
            xor_bytes(b"AB", b"A")

    def test_pack_unpack_u32(self):
        for val in [0, 1, 0xDEADBEEF, 0xFFFFFFFF]:
            assert unpack_u32_be(pack_u32_be(val)) == val

    def test_pack_unpack_u16(self):
        for val in [0, 1, 0xCAFE, 0xFFFF]:
            assert unpack_u16_be(pack_u16_be(val)) == val

    def test_bytes_to_bits_str(self):
        assert bytes_to_bits_str(b"\xA5") == "10100101"
        assert bytes_to_bits_str(b"\x00\xFF") == "0000000011111111"

    def test_bits_str_to_bytes_round_trip(self):
        data = b"\xDE\xAD\xBE\xEF"
        bits = bytes_to_bits_str(data)
        assert bits_str_to_bytes(bits) == data

    def test_bits_str_to_bytes_bad_length(self):
        with pytest.raises(ValueError):
            bits_str_to_bytes("1010")  # not multiple of 8
