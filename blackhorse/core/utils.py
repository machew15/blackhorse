"""
Shared utilities for the Blackhorse protocol.
"""

from __future__ import annotations

import struct
import zlib


def crc32(data: bytes | bytearray) -> int:
    """Return the CRC-32 checksum of *data* as an unsigned 32-bit integer."""
    return zlib.crc32(bytes(data)) & 0xFFFF_FFFF


def pack_u32_be(value: int) -> bytes:
    """Pack an unsigned integer into 4 bytes, big-endian."""
    return struct.pack(">I", value & 0xFFFF_FFFF)


def unpack_u32_be(data: bytes | bytearray, offset: int = 0) -> int:
    """Unpack a big-endian unsigned 32-bit integer from *data* at *offset*."""
    return struct.unpack_from(">I", data, offset)[0]


def pack_u16_be(value: int) -> bytes:
    """Pack an unsigned integer into 2 bytes, big-endian."""
    return struct.pack(">H", value & 0xFFFF)


def unpack_u16_be(data: bytes | bytearray, offset: int = 0) -> int:
    """Unpack a big-endian unsigned 16-bit integer from *data* at *offset*."""
    return struct.unpack_from(">H", data, offset)[0]


def xor_bytes(a: bytes, b: bytes) -> bytes:
    """XOR two equal-length byte strings and return the result."""
    if len(a) != len(b):
        raise ValueError(
            f"xor_bytes requires equal-length inputs (got {len(a)} and {len(b)})"
        )
    return bytes(x ^ y for x, y in zip(a, b))


def bytes_to_bits_str(data: bytes) -> str:
    """Return a human-readable binary string for *data* (e.g. '01001000...')."""
    return "".join(f"{b:08b}" for b in data)


def bits_str_to_bytes(bits: str) -> bytes:
    """Convert a binary string (multiples of 8) back to bytes."""
    if len(bits) % 8:
        raise ValueError("bits string length must be a multiple of 8")
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


def pad_to_block(data: bytes, block_size: int, pad_byte: int = 0) -> bytes:
    """Pad *data* to a multiple of *block_size* bytes."""
    rem = len(data) % block_size
    if rem:
        data = data + bytes([pad_byte] * (block_size - rem))
    return data
