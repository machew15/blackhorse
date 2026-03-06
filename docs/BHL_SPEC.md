# Blackhorse Language (BHL) Specification

**Version:** 1.0  
**Status:** Active  
**Protocol:** Blackhorse v1  

---

## 1. Overview

The Blackhorse Language (BHL) is the encoding layer at the heart of the
Blackhorse Protocol stack.  It occupies **Stage 2** of the seven-stage
pipeline, sitting above the Core Library (Stage 1) and below the
Compression Engine (Stage 3).

BHL is not ASCII.  It is not UTF-8.  It is a **Blackhorse-native**
variable-length binary encoding with the following design goals:

| Goal | Description |
|------|-------------|
| **Sovereign** | The symbol table is defined by this spec, not borrowed from Unicode or ASCII |
| **Compact** | Common bytes get shorter codes; the average is < 8 bits per input byte for English text |
| **Self-describing** | Every BHL stream carries a header that identifies the version, table, and length |
| **Prefix-free** | Codes are unambiguously decodable without lookahead |
| **Agnostic** | Any conforming parser (human or AI) can decode a BHL stream given only this document |

---

## 2. Symbol Tables

A **symbol table** defines the mapping from the 256 possible input byte
values to their BHL bit codes.  Each table is identified by a **Table ID**
(1 byte, 0–255).

### 2.1  Table ID 0 — Default (English-text optimised)

The default table partitions the 256 byte values into three frequency groups:

| Group | Positions | Code prefix | Code length | Count |
|-------|-----------|-------------|-------------|-------|
| A | 0 – 63 | `0` | 7 bits | 64 |
| B | 64 – 127 | `10` | 8 bits | 64 |
| C | 128 – 255 | `11` | 9 bits | 128 |
| **Total** | | | | **256** |

The groups are prefix-free by construction:
- A code in Group A starts with `0`; no Group B or C code starts with `0`.
- A code in Group B starts with `10`; no Group C code starts with `10`.
- A code in Group C starts with `11`.

#### 2.1.1  Group A — 7-bit codes (positions 0–63)

The following 64 bytes occupy Group A (most common in English text and
source code), listed in position order (position 0 first):

```
Pos  Byte  Char    Pos  Byte  Char    Pos  Byte  Char    Pos  Byte  Char
  0  0x20  SPACE    16  0x77  w        32  0x49  I        48  0x56  V
  1  0x65  e        17  0x67  g        33  0x4E  N        49  0x4B  K
  2  0x74  t        18  0x70  p        34  0x4F  O        50  0x4A  J
  3  0x61  a        19  0x79  y        35  0x52  R        51  0x58  X
  4  0x6F  o        20  0x62  b        36  0x4C  L        52  0x51  Q
  5  0x69  i        21  0x76  v        37  0x44  D        53  0x5A  Z
  6  0x6E  n        22  0x6B  k        38  0x43  C        54  0x2E  .
  7  0x73  s        23  0x6A  j        39  0x55  U        55  0x2C  ,
  8  0x72  r        24  0x78  x        40  0x4D  M        56  0x27  '
  9  0x68  h        25  0x71  q        41  0x46  F        57  0x22  "
 10  0x6C  l        26  0x7A  z        42  0x57  W        58  0x30  0
 11  0x64  d        27  0x0A  LF       43  0x47  G        59  0x31  1
 12  0x63  c        28  0x54  T        44  0x50  P        60  0x32  2
 13  0x75  u        29  0x41  A        45  0x59  Y        61  0x33  3
 14  0x6D  m        30  0x53  S        46  0x42  B        62  0x34  4
 15  0x66  f        31  0x48  H        47  0x45  E        63  0x09  HT
```

#### 2.1.2  Group B — 8-bit codes (positions 64–127)

```
Pos  Byte  Char    Pos  Byte  Char    Pos  Byte  Char    Pos  Byte  Char
 64  0x35  5        80  0x5F  _        96  0x04  EOT     112  0x1D  GS
 65  0x36  6        81  0x2F  /        97  0x05  ENQ     113  0x1E  RS
 66  0x37  7        82  0x5C  \        98  0x06  ACK     114  0x1F  US
 67  0x38  8        83  0x7C  |        99  0x07  BEL     115  0x7F  DEL
 68  0x39  9        84  0x40  @       100  0x08  BS      116  0x80  0x80
 69  0x21  !        85  0x23  #       101  0x1A  SUB     117  0x81  0x81
 70  0x3F  ?        86  0x24  $       102  0x1B  ESC     118  0x82  0x82
 71  0x3A  :        87  0x25  %       103  0x1C  FS      119  0x83  0x83
 72  0x3B  ;        88  0x26  &       104  …                  …
 73  0x28  (        89  0x2A  *       …
 74  0x29  )        90  0x2B  +
 75  0x5B  [        91  0x3D  =
 76  0x5D  ]        92  0x3C  <
 77  0x7B  {        93  0x3E  >
 78  0x7D  }        94  0x5E  ^
 79  0x2D  -        95  0x7E  ~
```

*(full table continues to position 127; see `blackhorse/language/symbols.py`)*

#### 2.1.3  Group C — 9-bit codes (positions 128–255)

All remaining 128 byte values sorted by value:
`0x0E, 0x0F, 0x10, 0x11, …, 0x19, 0x8C, 0x8D, …, 0xFF`

*(full table in `blackhorse/language/symbols.py` — `_LOW_FREQ` list)*

---

## 3. Code Assignment

Given a byte value `b`, its BHL code is determined by:

1. Look up `pos = TABLE_ENCODE[b]`  (the byte's position in the ordered table).
2. Compute code bits:

```
if pos < 64:
    write 7 bits: pos                   # 0b0_pppppp
elif pos < 128:
    write 8 bits: 0x80 | (pos - 64)    # 0b10_pppppp
else:
    write 9 bits: 0x180 | (pos - 128)  # 0b11_ppppppp
```

All bits are written **MSB-first**.

### 3.1  Encoding Example

Input: `"Hi"` = `[0x48, 0x69]`

| Byte | Char | Position | Code   | Bits (MSB first) |
|------|------|----------|--------|-----------------|
| 0x48 | H    | 31       | 0x1F   | `0 011111`       |
| 0x69 | i    | 5        | 0x05   | `0 000101`       |

Combined bit stream: `0011111 0000101` = 14 bits

Padded to 2 bytes: `0b00111110 0b00101 0b00` = `0x3E 0x14` (with 2 trailing zeros)

---

## 4. Decoding Algorithm

```
read_bhl_symbol(stream):
    b0 = stream.read_bit()
    if b0 == 0:
        pos = stream.read_bits(6)           # Group A
    else:
        b1 = stream.read_bit()
        if b1 == 0:
            pos = 64 + stream.read_bits(6)  # Group B
        else:
            pos = 128 + stream.read_bits(7) # Group C
    return TABLE_ORDER[pos]
```

Repeat until `bit_count` bits have been consumed (as recorded in the packet header).

---

## 5. Packet Format

Every BHL-encoded message is wrapped in a self-describing **BHL Packet**:

```
Offset  Size  Field        Description
──────  ────  ───────────  ──────────────────────────────────────────────
0       4     Magic        b'BHL\x1A'  (ASCII "BHL" + control char 0x1A)
4       1     Version      0x01
5       1     Table ID     0x00 = Table 0 (default)
6       1     Flags        0x00 (see §5.1)
7       4     Bit Count    Number of meaningful payload bits (uint32 BE)
11      var   Payload      BHL bit-packed data, padded to byte boundary
11+P    4     CRC32        CRC-32 of bytes [0 : 11+P]  (uint32 BE)
```

`P` = ⌈Bit Count / 8⌉ bytes.

Minimum packet size: 11 + 0 + 4 = **15 bytes**.

### 5.1  Flags Byte

| Bit | Mask | Meaning |
|-----|------|---------|
| 0   | 0x01 | `COMPRESSED` — payload was compressed before BHL encoding |
| 1   | 0x02 | `ENCRYPTED` — additional encryption layer present |
| 2–7 | —    | Reserved; must be 0 |

---

## 6. Performance Characteristics

For typical English text (letters, spaces, punctuation):

| Metric | Value |
|--------|-------|
| Average bits/byte (uniform distribution) | 8.25 |
| Average bits/byte (English text, Group A) | ~7.0 |
| Compression ratio vs. ASCII | ~12.5% saving |
| Compression ratio vs. UTF-8 (ASCII subset) | same |

BHL is not a general-purpose compressor.  Its benefit over raw bytes is
modest (~1 bit/byte for English text).  The real gain comes from the
**Stage 3 LZ77 compressor** operating on the BHL stream.

---

## 7. Interoperability Requirements

A conforming BHL implementation MUST:

1. Support Table ID 0 (the default table defined in §2.1).
2. Accept packets with any `Bit Count` in [0, 2³²−1].
3. Reject packets with an invalid magic (`b'BHL\x1A'`) or CRC mismatch.
4. Ignore unknown flag bits (forward compatibility).
5. Write bits MSB-first within each byte.

A conforming BHL implementation MAY:

- Support additional table IDs (1–255) via a table registry.
- Add new flag bits in a backwards-compatible way.

---

## 8. Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-03-06 | Initial specification |

---

*Blackhorse Protocol — your IP, your spec, your continuity.*
