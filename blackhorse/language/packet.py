"""
BHL Packet — wire format for a Blackhorse Language stream.

Packet layout (all multi-byte integers are big-endian):

  ┌──────────────────────────────────────────────────────────────┐
  │ HEADER (11 bytes)                                            │
  │   Magic    : 4 bytes  b'BHL\\x1A'                            │
  │   Version  : 1 byte   0x01                                  │
  │   Table ID : 1 byte   0x00 = default                        │
  │   Flags    : 1 byte   see FLAG_* constants below            │
  │   Bit Count: 4 bytes  number of payload bits (uint32 BE)    │
  ├──────────────────────────────────────────────────────────────┤
  │ PAYLOAD  (⌈bit_count / 8⌉ bytes)                            │
  │   BHL bit-packed encoded data; trailing bits are zero-padded │
  ├──────────────────────────────────────────────────────────────┤
  │ FOOTER (4 bytes)                                             │
  │   CRC32    : 4 bytes  CRC-32 of header + payload            │
  └──────────────────────────────────────────────────────────────┘

Minimum packet size: 11 + 0 + 4 = 15 bytes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.utils import crc32, pack_u32_be, unpack_u32_be

BHL_MAGIC: bytes = b"BHL\x1A"
BHL_VERSION: int = 0x01

HEADER_SIZE: int = 11   # magic(4) + version(1) + table_id(1) + flags(1) + bit_count(4)
FOOTER_SIZE: int = 4    # CRC32

# Flags byte bit-masks
FLAG_NONE: int = 0x00


class BHLError(Exception):
    """Raised when a BHL packet is malformed or invalid."""


@dataclass
class BHLPacket:
    """
    Parsed representation of a BHL packet.

    Attributes
    ----------
    version   : BHL version (currently always 1).
    table_id  : Symbol table identifier (0 = default).
    flags     : Flags byte.
    bit_count : Number of meaningful payload bits.
    payload   : Raw payload bytes (may include trailing zero-padding).
    """

    version: int
    table_id: int
    flags: int
    bit_count: int
    payload: bytes

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialise the packet to bytes including header and CRC footer."""
        header = (
            BHL_MAGIC
            + bytes([self.version, self.table_id, self.flags])
            + pack_u32_be(self.bit_count)
        )
        body = header + self.payload
        footer = pack_u32_be(crc32(body))
        return body + footer

    # ------------------------------------------------------------------
    # Deserialisation
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes) -> "BHLPacket":
        """
        Parse a BHL packet from raw bytes.

        Raises ``BHLError`` if the magic, version, or checksum is invalid.
        """
        if len(data) < HEADER_SIZE + FOOTER_SIZE:
            raise BHLError(
                f"Packet too short: {len(data)} bytes "
                f"(minimum {HEADER_SIZE + FOOTER_SIZE})"
            )

        magic = data[:4]
        if magic != BHL_MAGIC:
            raise BHLError(
                f"Invalid BHL magic: {magic!r} (expected {BHL_MAGIC!r})"
            )

        version = data[4]
        if version != BHL_VERSION:
            raise BHLError(
                f"Unsupported BHL version: {version} (expected {BHL_VERSION})"
            )

        table_id = data[5]
        flags = data[6]
        bit_count = unpack_u32_be(data, 7)

        payload_byte_len = math.ceil(bit_count / 8) if bit_count else 0
        expected_total = HEADER_SIZE + payload_byte_len + FOOTER_SIZE

        if len(data) < expected_total:
            raise BHLError(
                f"Packet truncated: got {len(data)} bytes, "
                f"expected {expected_total}"
            )

        payload = data[HEADER_SIZE : HEADER_SIZE + payload_byte_len]

        stored_crc = unpack_u32_be(data, HEADER_SIZE + payload_byte_len)
        computed_crc = crc32(data[: HEADER_SIZE + payload_byte_len])
        if stored_crc != computed_crc:
            raise BHLError(
                f"CRC mismatch: stored 0x{stored_crc:08X}, "
                f"computed 0x{computed_crc:08X}"
            )

        return cls(
            version=version,
            table_id=table_id,
            flags=flags,
            bit_count=bit_count,
            payload=payload,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        payload_bits: bytes,
        bit_count: int,
        table_id: int = 0,
        flags: int = FLAG_NONE,
    ) -> "BHLPacket":
        """Convenience constructor: build a packet from a bit buffer."""
        return cls(
            version=BHL_VERSION,
            table_id=table_id,
            flags=flags,
            bit_count=bit_count,
            payload=payload_bits,
        )

    def __repr__(self) -> str:
        return (
            f"BHLPacket(version={self.version}, table_id={self.table_id}, "
            f"flags=0x{self.flags:02X}, bit_count={self.bit_count}, "
            f"payload_bytes={len(self.payload)})"
        )
