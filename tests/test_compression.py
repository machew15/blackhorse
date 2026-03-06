"""Tests for Stage 3 — Blackhorse Compression Engine."""

import pytest

from blackhorse.compression import Compressor, Decompressor, compress, decompress
from blackhorse.compression.engine import CompressorError, COMP_MAGIC


class TestCompressor:
    def test_empty_data(self):
        assert decompress(compress(b"")) == b""

    def test_single_byte(self):
        data = b"\x42"
        assert decompress(compress(data)) == data

    def test_ascii_text_round_trip(self):
        data = b"Hello, Blackhorse Protocol!"
        assert decompress(compress(data)) == data

    def test_binary_data_round_trip(self):
        data = bytes(range(256))
        assert decompress(compress(data)) == data

    def test_repetitive_data_compresses(self):
        data = b"AAAAAAAAAAAAAAAA" * 64   # 1024 bytes of 'A'
        compressed = compress(data)
        assert decompress(compressed) == data
        assert len(compressed) < len(data), \
            "Highly repetitive data should compress well"

    def test_long_text_round_trip(self):
        text = b"the quick brown fox jumps over the lazy dog " * 50
        assert decompress(compress(text)) == text

    def test_longer_binary_round_trip(self):
        import os
        data = bytes(i % 256 for i in range(4096))
        assert decompress(compress(data)) == data

    def test_compressed_has_magic_header(self):
        compressed = compress(b"test data")
        assert compressed[:3] == COMP_MAGIC

    def test_decompressor_rejects_bad_magic(self):
        bad = b"XYZ\x01" + b"\x00" * 20
        with pytest.raises(CompressorError):
            decompress(bad)

    def test_decompressor_rejects_bad_crc(self):
        compressed = bytearray(compress(b"some data here and there"))
        compressed[-1] ^= 0xFF
        with pytest.raises(CompressorError):
            decompress(bytes(compressed))

    def test_window_bits_parameter(self):
        data = b"ABCABC" * 100
        c8 = Compressor(window_bits=8)
        c12 = Compressor(window_bits=12)
        d = Decompressor()
        assert d.decompress(c8.compress(data)) == data
        assert d.decompress(c12.compress(data)) == data

    def test_invalid_window_bits(self):
        with pytest.raises(ValueError):
            Compressor(window_bits=4)

    def test_large_data_round_trip(self):
        # 10 KB of mixed data
        import random
        rng = random.Random(42)
        data = bytes(rng.randint(0, 255) for _ in range(10_000))
        assert decompress(compress(data)) == data

    def test_repeated_pattern_compresses_well(self):
        pattern = b"sovereign AI collaboration "
        data = pattern * 200
        compressed = compress(data)
        assert len(compressed) < len(data) // 2
        assert decompress(compressed) == data
