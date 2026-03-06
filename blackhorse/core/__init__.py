"""Stage 1 — Blackhorse Core Library: bit primitives, buffers, streams."""

from .bitstream import BitStream
from .ringbuffer import RingBuffer
from .utils import crc32, xor_bytes, pack_u32_be, unpack_u32_be, bytes_to_bits_str

__all__ = [
    "BitStream",
    "RingBuffer",
    "crc32",
    "xor_bytes",
    "pack_u32_be",
    "unpack_u32_be",
    "bytes_to_bits_str",
]
