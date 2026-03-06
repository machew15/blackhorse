"""
BHL Symbol Tables
=================

Every BHL table maps each of the 256 possible byte values to a
variable-length, prefix-free bit code.

Table 0 — Default (English-text optimised)
-------------------------------------------
The 256 byte values are partitioned into three frequency groups:

  Group A (positions  0–63):  64 symbols → **7-bit** codes  (prefix ``0``)
  Group B (positions 64–127): 64 symbols → **8-bit** codes  (prefix ``10``)
  Group C (positions 128–255):128 symbols → **9-bit** codes (prefix ``11``)

Code assignment (unambiguous, prefix-free):

  Position p in Group A:  write 7 bits = p          (0b0_pppppp)
  Position p in Group B:  write 8 bits = 0x80|(p-64) (0b10_pppppp)
  Position p in Group C:  write 9 bits = 0x180|(p-128)(0b11_ppppppp)

Decode path:
  Read 1 bit.
    0 → read 6 more bits → position = those 6 bits (Group A)
    1 → read 1 more bit:
          0 → read 6 more bits → position = 64 + those 6 bits  (Group B)
          1 → read 7 more bits → position = 128 + those 7 bits (Group C)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Table 0 — Default symbol ordering
# ---------------------------------------------------------------------------
# Each list contains byte values in decreasing frequency order.
# The *position* of a byte in the combined TABLE_0_ORDER list determines
# its code length and code value.

_HIGH_FREQ: list[int] = [
    # 64 most common bytes in English text + source code  (→ 7-bit codes)
    0x20, 0x65, 0x74, 0x61, 0x6F, 0x69, 0x6E, 0x73,  # ' ' e t a o i n s
    0x72, 0x68, 0x6C, 0x64, 0x63, 0x75, 0x6D, 0x66,  # r h l d c u m f
    0x77, 0x67, 0x70, 0x79, 0x62, 0x76, 0x6B, 0x6A,  # w g p y b v k j
    0x78, 0x71, 0x7A, 0x0A, 0x54, 0x41, 0x53, 0x48,  # x q z \n T A S H
    0x49, 0x4E, 0x4F, 0x52, 0x4C, 0x44, 0x43, 0x55,  # I N O R L D C U
    0x4D, 0x46, 0x57, 0x47, 0x50, 0x59, 0x42, 0x45,  # M F W G P Y B E
    0x56, 0x4B, 0x4A, 0x58, 0x51, 0x5A, 0x2E, 0x2C,  # V K J X Q Z . ,
    0x27, 0x22, 0x30, 0x31, 0x32, 0x33, 0x34, 0x09,  # ' " 0 1 2 3 4 \t
]

_MED_FREQ: list[int] = [
    # 64 moderately common bytes  (→ 8-bit codes)
    0x35, 0x36, 0x37, 0x38, 0x39, 0x21, 0x3F, 0x3A,  # 5 6 7 8 9 ! ? :
    0x3B, 0x28, 0x29, 0x5B, 0x5D, 0x7B, 0x7D, 0x2D,  # ; ( ) [ ] { } -
    0x5F, 0x2F, 0x5C, 0x7C, 0x40, 0x23, 0x24, 0x25,  # _ / \ | @ # $ %
    0x26, 0x2A, 0x2B, 0x3D, 0x3C, 0x3E, 0x5E, 0x7E,  # & * + = < > ^ ~
    0x60, 0x0D, 0x0B, 0x0C, 0x00, 0x01, 0x02, 0x03,  # ` \r \v \f NUL SOH STX ETX
    0x04, 0x05, 0x06, 0x07, 0x08, 0x1A, 0x1B, 0x1C,  # EOT ENQ ACK BEL BS SUB ESC FS
    0x1D, 0x1E, 0x1F, 0x7F, 0x80, 0x81, 0x82, 0x83,  # GS RS US DEL 0x80–0x83
    0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A, 0x8B,  # 0x84–0x8B
]

_USED: frozenset[int] = frozenset(_HIGH_FREQ + _MED_FREQ)

# Remaining 128 bytes sorted by value  (→ 9-bit codes)
_LOW_FREQ: list[int] = sorted(b for b in range(256) if b not in _USED)

assert len(_HIGH_FREQ) == 64, "High-freq table must have exactly 64 entries"
assert len(_MED_FREQ) == 64, "Med-freq table must have exactly 64 entries"
assert len(_LOW_FREQ) == 128, "Low-freq table must have exactly 128 entries"
assert len(set(_HIGH_FREQ + _MED_FREQ + _LOW_FREQ)) == 256, \
    "Symbol tables must cover all 256 byte values without duplicates"

# Combined ordered list: index → byte value
TABLE_0_ORDER: list[int] = _HIGH_FREQ + _MED_FREQ + _LOW_FREQ

# Reverse map: byte value → position (for O(1) encoding)
TABLE_0_ENCODE: dict[int, int] = {b: i for i, b in enumerate(TABLE_0_ORDER)}

# Registry of all tables keyed by Table ID
TABLES: dict[int, tuple[list[int], dict[int, int]]] = {
    0: (TABLE_0_ORDER, TABLE_0_ENCODE),
}


def get_table(table_id: int) -> tuple[list[int], dict[int, int]]:
    """Return ``(order_list, encode_map)`` for *table_id*.

    Raises ``KeyError`` for unknown table IDs.
    """
    if table_id not in TABLES:
        raise KeyError(f"Unknown BHL table ID: {table_id}")
    return TABLES[table_id]


def code_for_position(pos: int) -> tuple[int, int]:
    """Return ``(code_value, code_length_bits)`` for a symbol at *pos*."""
    if pos < 64:
        return pos, 7                       # 0b0_pppppp  (7 bits)
    if pos < 128:
        return 0x80 | (pos - 64), 8        # 0b10_pppppp (8 bits)
    return 0x180 | (pos - 128), 9          # 0b11_ppppppp (9 bits)


def average_bits_per_byte(table_id: int = 0) -> float:
    """Return the average code length for a uniform byte distribution."""
    order, _ = get_table(table_id)
    total = sum(code_for_position(i)[1] for i in range(len(order)))
    return total / len(order)
