"""
BHLEncoder — encode bytes (or str) into a BHL packet.

Encoding algorithm
------------------
For each input byte *b*:
  1. Look up its position *p* in the active symbol table.
  2. Emit bits according to the group:
       p < 64   → write 7 bits: value = p          (prefix `0`)
       p < 128  → write 8 bits: value = 0x80|(p-64) (prefix `10`)
       p < 256  → write 9 bits: value = 0x180|(p-128)(prefix `11`)

The resulting bit stream is wrapped in a BHLPacket for transport.
"""

from __future__ import annotations

from ..core.bitstream import BitStream
from .packet import BHLPacket, FLAG_NONE
from .symbols import code_for_position, get_table


class BHLEncoder:
    """
    Encodes arbitrary bytes (or UTF-8 text) into a BHL packet.

    Parameters
    ----------
    table_id : int
        Symbol table to use (0 = default).
    """

    def __init__(self, table_id: int = 0) -> None:
        self._table_id = table_id
        _, self._encode_map = get_table(table_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encode(self, text: str, encoding: str = "utf-8") -> bytes:
        """
        Encode a text string and return the serialised BHL packet bytes.

        Parameters
        ----------
        text     : The string to encode.
        encoding : The text codec to use before BHL encoding (default UTF-8).

        Returns
        -------
        bytes
            A fully serialised BHL packet (header + payload + CRC).
        """
        return self.encode_bytes(text.encode(encoding))

    def encode_bytes(self, data: bytes | bytearray) -> bytes:
        """
        Encode raw bytes and return the serialised BHL packet bytes.

        Parameters
        ----------
        data : The bytes to encode.

        Returns
        -------
        bytes
            A fully serialised BHL packet.
        """
        stream = self._encode_to_stream(data)
        packet = BHLPacket.build(
            payload_bits=stream.to_bytes(),
            bit_count=stream.bit_length,
            table_id=self._table_id,
            flags=FLAG_NONE,
        )
        return packet.to_bytes()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encode_to_stream(self, data: bytes | bytearray) -> BitStream:
        """Encode *data* into a BitStream without the packet wrapper."""
        stream = BitStream()
        encode_map = self._encode_map
        for byte in data:
            pos = encode_map[byte]
            code, length = code_for_position(pos)
            stream.write_bits(code, length)
        return stream

    def encode_to_bitstream(self, data: bytes | bytearray) -> BitStream:
        """Encode *data* and return the raw BitStream (no packet wrapper)."""
        return self._encode_to_stream(data)

    @property
    def table_id(self) -> int:
        return self._table_id
