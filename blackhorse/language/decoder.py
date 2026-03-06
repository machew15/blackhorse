"""
BHLDecoder — decode a BHL packet back to bytes (or str).

Decoding algorithm
------------------
Read bits one at a time from the payload BitStream:

  Read 1 bit:
    0 → read 6 more bits → position = those 6 bits            (Group A, 7-bit)
    1 → read 1 more bit:
          0 → read 6 more bits → position = 64  + those 6 bits (Group B, 8-bit)
          1 → read 7 more bits → position = 128 + those 7 bits (Group C, 9-bit)

  Look up TABLE_ORDER[position] → decoded byte value.

Repeat until *bit_count* bits have been consumed.
"""

from __future__ import annotations

from ..core.bitstream import BitStream
from .packet import BHLPacket, BHLError
from .symbols import get_table


class BHLDecoder:
    """
    Decodes a BHL packet back to bytes or a UTF-8 string.

    Parameters
    ----------
    table_id : int
        Symbol table to use; normally read from the packet header.
        This value is used as a fallback if the caller provides a raw
        BitStream instead of a full packet.
    """

    def __init__(self, table_id: int = 0) -> None:
        self._default_table_id = table_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decode(self, packet_bytes: bytes, encoding: str = "utf-8") -> str:
        """
        Decode a serialised BHL packet and return the original string.

        Parameters
        ----------
        packet_bytes : Bytes produced by ``BHLEncoder.encode``.
        encoding     : Text codec used to decode the recovered bytes.

        Returns
        -------
        str
        """
        raw = self.decode_bytes(packet_bytes)
        return raw.decode(encoding)

    def decode_bytes(self, packet_bytes: bytes) -> bytes:
        """
        Decode a serialised BHL packet and return the original bytes.

        Parameters
        ----------
        packet_bytes : Bytes produced by ``BHLEncoder.encode_bytes``.

        Returns
        -------
        bytes
        """
        packet = BHLPacket.from_bytes(packet_bytes)
        return self._decode_packet(packet)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _decode_packet(self, packet: BHLPacket) -> bytes:
        """Decode a parsed ``BHLPacket`` to raw bytes."""
        order, _ = get_table(packet.table_id)
        stream = BitStream.from_bytes(packet.payload)
        return self._decode_stream(stream, packet.bit_count, order)

    def _decode_stream(
        self, stream: BitStream, bit_count: int, order: list[int]
    ) -> bytes:
        """
        Read exactly *bit_count* bits from *stream* and decode them.

        Parameters
        ----------
        stream    : A ``BitStream`` positioned at the start of the payload.
        bit_count : Total bits that were written during encoding.
        order     : Symbol-table order list for the active table.
        """
        out = bytearray()
        consumed = 0

        while consumed < bit_count:
            remaining = bit_count - consumed

            # Need at least 7 bits for the shortest code.
            if remaining < 7:
                break

            first = stream.read_bit()
            consumed += 1

            if first == 0:
                # Group A: 7-bit code = 0 + 6 bits
                if remaining < 7:
                    raise BHLError("Truncated Group-A code in payload")
                pos = stream.read_bits(6)
                consumed += 6
            else:
                second = stream.read_bit()
                consumed += 1
                if second == 0:
                    # Group B: 8-bit code = 10 + 6 bits
                    if remaining < 8:
                        raise BHLError("Truncated Group-B code in payload")
                    pos = 64 + stream.read_bits(6)
                    consumed += 6
                else:
                    # Group C: 9-bit code = 11 + 7 bits
                    if remaining < 9:
                        raise BHLError("Truncated Group-C code in payload")
                    pos = 128 + stream.read_bits(7)
                    consumed += 7

            if pos >= len(order):
                raise BHLError(f"Symbol position {pos} out of range for table")
            out.append(order[pos])

        return bytes(out)

    def decode_bitstream(
        self,
        stream: BitStream,
        bit_count: int,
        table_id: int | None = None,
    ) -> bytes:
        """Decode from a raw BitStream without a packet wrapper."""
        tid = table_id if table_id is not None else self._default_table_id
        order, _ = get_table(tid)
        return self._decode_stream(stream, bit_count, order)
