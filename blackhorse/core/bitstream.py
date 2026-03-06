"""
BitStream — bit-level read/write over a growable byte buffer.

All bits are stored and transmitted MSB-first (most significant bit first).
The write position and read position are tracked independently.
"""

from __future__ import annotations


class BitStream:
    """
    A mutable bit-level stream backed by a bytearray.

    Write bits sequentially with ``write_bit`` / ``write_bits``.
    Read them back with ``read_bit`` / ``read_bits``.

    MSB-first ordering: the first bit written occupies bit 7 of byte 0,
    the eighth bit written occupies bit 0 of byte 0, the ninth bit starts
    byte 1 at bit 7, and so on.
    """

    def __init__(self, data: bytes | bytearray | None = None) -> None:
        if data is not None:
            self._buf: bytearray = bytearray(data)
            self._write_pos: int = len(self._buf) * 8
        else:
            self._buf = bytearray()
            self._write_pos = 0
        self._read_pos: int = 0

    # ------------------------------------------------------------------
    # Write interface
    # ------------------------------------------------------------------

    def write_bit(self, bit: int) -> None:
        """Write a single bit (0 or 1) at the current write position."""
        byte_idx = self._write_pos >> 3
        bit_idx = 7 - (self._write_pos & 7)   # MSB first within each byte
        if byte_idx >= len(self._buf):
            self._buf.append(0)
        if bit:
            self._buf[byte_idx] |= 1 << bit_idx
        else:
            self._buf[byte_idx] &= ~(1 << bit_idx) & 0xFF
        self._write_pos += 1

    def write_bits(self, value: int, num_bits: int) -> None:
        """Write the lowest *num_bits* bits of *value*, MSB first."""
        for shift in range(num_bits - 1, -1, -1):
            self.write_bit((value >> shift) & 1)

    def write_byte(self, byte: int) -> None:
        """Write a single byte (8 bits)."""
        self.write_bits(byte & 0xFF, 8)

    def write_bytes(self, data: bytes | bytearray) -> None:
        """Write all bytes in *data*."""
        for b in data:
            self.write_byte(b)

    # ------------------------------------------------------------------
    # Read interface
    # ------------------------------------------------------------------

    def read_bit(self) -> int:
        """Read a single bit; raises ``EOFError`` when the stream is exhausted."""
        if self._read_pos >= self._write_pos:
            raise EOFError("BitStream exhausted")
        byte_idx = self._read_pos >> 3
        bit_idx = 7 - (self._read_pos & 7)
        self._read_pos += 1
        return (self._buf[byte_idx] >> bit_idx) & 1

    def read_bits(self, num_bits: int) -> int:
        """Read *num_bits* bits and return as an integer (MSB first)."""
        result = 0
        for _ in range(num_bits):
            result = (result << 1) | self.read_bit()
        return result

    def read_byte(self) -> int:
        """Read 8 bits as an integer 0–255."""
        return self.read_bits(8)

    def read_bytes(self, count: int) -> bytes:
        """Read *count* bytes."""
        return bytes(self.read_byte() for _ in range(count))

    # ------------------------------------------------------------------
    # Seek / introspection
    # ------------------------------------------------------------------

    def seek_read(self, bit_pos: int) -> None:
        """Move the read cursor to *bit_pos*."""
        if bit_pos < 0 or bit_pos > self._write_pos:
            raise ValueError(f"Bit position {bit_pos} out of range [0, {self._write_pos}]")
        self._read_pos = bit_pos

    def rewind(self) -> None:
        """Reset the read cursor to the beginning."""
        self._read_pos = 0

    @property
    def bit_length(self) -> int:
        """Total number of bits that have been written."""
        return self._write_pos

    @property
    def bits_remaining(self) -> int:
        """Bits available for reading from the current read position."""
        return self._write_pos - self._read_pos

    @property
    def read_pos(self) -> int:
        """Current read cursor position in bits."""
        return self._read_pos

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """
        Return the underlying buffer as ``bytes``.

        The buffer is always padded to a full byte boundary with trailing
        zero-bits.  The caller should use ``bit_length`` to know where
        meaningful content ends.
        """
        return bytes(self._buf)

    @classmethod
    def from_bytes(cls, data: bytes) -> "BitStream":
        """Create a ``BitStream`` pre-loaded with *data*, read position at 0."""
        obj = cls(data)
        obj._read_pos = 0
        return obj

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return self._write_pos

    def __repr__(self) -> str:
        return (
            f"BitStream(bits={self._write_pos}, "
            f"read_pos={self._read_pos}, "
            f"bytes={len(self._buf)})"
        )
