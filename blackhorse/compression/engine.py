"""
Blackhorse Compression Engine — LZ77 over the BHL-encoded byte stream.

Wire format
-----------
  ┌──────────────────────────────────────────────────────────────┐
  │ COMP HEADER (12 bytes)                                       │
  │   Magic        : 3 bytes  b'LZB'                            │
  │   Version      : 1 byte   0x01                              │
  │   Flags        : 1 byte   0x00 (reserved)                   │
  │   Window bits  : 1 byte   log2 of look-behind window size   │
  │   Original size: 4 bytes  uint32 BE                         │
  │   Reserved     : 2 bytes  0x00 0x00                         │
  ├──────────────────────────────────────────────────────────────┤
  │ BLOCKS                                                       │
  │  Each block starts with a 1-byte FLAGS word.                 │
  │  Each bit in FLAGS (MSB first) represents one item:         │
  │    0 → next item is a LITERAL  (1 byte)                     │
  │    1 → next item is a MATCH    (3 bytes):                   │
  │          byte 0: high 8 bits of offset                      │
  │          byte 1: low  4 bits of offset || length-3 (4 bits) │
  │          — offset range: 1–4096; length range: 3–18        │
  ├──────────────────────────────────────────────────────────────┤
  │ COMP FOOTER (4 bytes)                                        │
  │   CRC32 of header + blocks                                  │
  └──────────────────────────────────────────────────────────────┘

The compressor operates on the *BHL packet bytes* produced by Stage 2.
Apply ``BHLEncoder.encode_bytes`` first, then ``compress`` the result.
"""

from __future__ import annotations

import struct

from ..core.ringbuffer import RingBuffer
from ..core.utils import crc32, pack_u32_be, unpack_u32_be

COMP_MAGIC: bytes = b"LZB"
COMP_VERSION: int = 0x01
HEADER_SIZE: int = 12  # magic(3) + version(1) + flags(1) + window_bits(1) + orig_size(4) + reserved(2)
FOOTER_SIZE: int = 4

DEFAULT_WINDOW_BITS: int = 12          # 2^12 = 4096-byte look-behind window
MIN_MATCH: int = 3
MAX_MATCH: int = 18                    # fits in 4 bits (value stored as len-3)
ITEMS_PER_BLOCK: int = 8


class CompressorError(Exception):
    """Raised when compressed data is invalid."""


def _build_header(original_size: int, window_bits: int, flags: int = 0) -> bytes:
    return (
        COMP_MAGIC
        + bytes([COMP_VERSION, flags, window_bits])
        + pack_u32_be(original_size)
        + b"\x00\x00"          # reserved
    )


def _parse_header(data: bytes) -> tuple[int, int, int]:
    """Return ``(original_size, window_bits, flags)``."""
    if len(data) < HEADER_SIZE:
        raise CompressorError(
            f"Compressed data too short: {len(data)} < {HEADER_SIZE}"
        )
    magic = data[:3]
    if magic != COMP_MAGIC:
        raise CompressorError(f"Invalid compression magic: {magic!r}")
    version = data[3]
    if version != COMP_VERSION:
        raise CompressorError(f"Unsupported compression version: {version}")
    flags = data[4]
    window_bits = data[5]
    original_size = unpack_u32_be(data, 6)
    return original_size, window_bits, flags


class Compressor:
    """
    LZ77 compressor.

    Parameters
    ----------
    window_bits : int
        Base-2 logarithm of the look-behind window size.
        12 → 4 096 bytes  (default)
        16 → 65 536 bytes (better compression, slower)
    """

    def __init__(self, window_bits: int = DEFAULT_WINDOW_BITS) -> None:
        if not (8 <= window_bits <= 16):
            raise ValueError("window_bits must be between 8 and 16")
        self._window_bits = window_bits
        self._window_size = 1 << window_bits

    def compress(self, data: bytes) -> bytes:
        """
        Compress *data* and return the compressed bytes (with header/footer).
        """
        if not data:
            header = _build_header(0, self._window_bits)
            footer = pack_u32_be(crc32(header))
            return header + footer

        window = RingBuffer(self._window_size)
        blocks: bytearray = bytearray()

        pos = 0
        n = len(data)

        while pos < n:
            # Collect up to ITEMS_PER_BLOCK items.
            flag_byte = 0
            items: list[bytes] = []

            for bit_idx in range(ITEMS_PER_BLOCK):
                if pos >= n:
                    break

                lookahead = data[pos : pos + MAX_MATCH]
                offset, length = window.find_match(lookahead, MIN_MATCH)

                if length >= MIN_MATCH:
                    # Encode a back-reference.
                    flag_byte |= 1 << (7 - bit_idx)
                    # offset: 12 bits (1–4096), length-3: 4 bits (0–15)
                    enc_offset = min(offset, self._window_size) - 1   # 0-based
                    enc_len = length - MIN_MATCH                       # 0–15
                    # Pack: [OOOOOOOO][OOOO_LLLL]
                    b0 = (enc_offset >> 4) & 0xFF
                    b1 = ((enc_offset & 0x0F) << 4) | (enc_len & 0x0F)
                    items.append(bytes([b0, b1]))
                    for i in range(length):
                        window.push(data[pos + i])
                    pos += length
                else:
                    # Encode a literal.
                    items.append(bytes([data[pos]]))
                    window.push(data[pos])
                    pos += 1

            blocks.append(flag_byte)
            for item in items:
                blocks.extend(item)

        header = _build_header(len(data), self._window_bits)
        body = header + bytes(blocks)
        footer = pack_u32_be(crc32(body))
        return body + footer


class Decompressor:
    """LZ77 decompressor (inverse of ``Compressor``)."""

    def decompress(self, data: bytes) -> bytes:
        """
        Decompress *data* produced by ``Compressor.compress``.

        Raises ``CompressorError`` on invalid input.
        """
        original_size, window_bits, _flags = _parse_header(data)

        stored_crc = unpack_u32_be(data, len(data) - FOOTER_SIZE)
        computed_crc = crc32(data[: len(data) - FOOTER_SIZE])
        if stored_crc != computed_crc:
            raise CompressorError(
                f"CRC mismatch in compressed stream: "
                f"stored 0x{stored_crc:08X}, computed 0x{computed_crc:08X}"
            )

        if original_size == 0:
            return b""

        window_size = 1 << window_bits
        window = RingBuffer(window_size)
        out = bytearray()
        pos = HEADER_SIZE
        end = len(data) - FOOTER_SIZE

        while pos < end and len(out) < original_size:
            if pos >= end:
                break
            flag_byte = data[pos]
            pos += 1

            for bit_idx in range(ITEMS_PER_BLOCK):
                if pos >= end or len(out) >= original_size:
                    break
                is_match = (flag_byte >> (7 - bit_idx)) & 1

                if is_match:
                    if pos + 2 > end:
                        raise CompressorError("Truncated match token")
                    b0 = data[pos]
                    b1 = data[pos + 1]
                    pos += 2
                    # enc_offset was stored as (original_offset - 1); restore to 1-based.
                    enc_offset = ((b0 << 4) | (b1 >> 4)) + 1
                    length = (b1 & 0x0F) + MIN_MATCH

                    if enc_offset > len(out):
                        raise CompressorError(
                            f"Match offset {enc_offset} exceeds decoded output "
                            f"length {len(out)}"
                        )

                    # Copy from the already-decoded output, NOT from the ring
                    # buffer.  Indexing directly into `out` is the only safe
                    # approach because the ring buffer's head pointer advances
                    # with each push, invalidating any pre-computed start index.
                    # Reading from `out` also handles run-length overlapping
                    # copies naturally (when copy_start + i >= len_before_copy).
                    copy_start = len(out) - enc_offset
                    for i in range(length):
                        if len(out) >= original_size:
                            break
                        byte_val = out[copy_start + i]
                        out.append(byte_val)
                        window.push(byte_val)
                else:
                    if pos >= end:
                        raise CompressorError("Truncated literal token")
                    byte_val = data[pos]
                    pos += 1
                    out.append(byte_val)
                    window.push(byte_val)

        return bytes(out[:original_size])


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def compress(data: bytes, window_bits: int = DEFAULT_WINDOW_BITS) -> bytes:
    """Compress *data* using the Blackhorse LZ77 engine."""
    return Compressor(window_bits).compress(data)


def decompress(data: bytes) -> bytes:
    """Decompress *data* produced by ``compress``."""
    return Decompressor().decompress(data)
