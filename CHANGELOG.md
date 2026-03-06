# Changelog

All notable changes to the Blackhorse Protocol are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Each entry notes the AI model and date — this project is designed for
continuity across AI sessions and collaborative authorship is explicit.

---

## [0.1.0] — 2026-03-06

*claude-4.6-sonnet-high-thinking | 2026-03-06 | Initial complete implementation*

### Added — Stage 1: Core Library (`blackhorse/core/`)

- **`BitStream`** — MSB-first bit-level read/write over a growable `bytearray`.
  Supports arbitrary-width reads/writes, seek, and rewind.
- **`RingBuffer`** — Fixed-capacity circular buffer with O(1) indexed access
  and a `find_match()` method for LZ77 look-behind searching.
- **`utils`** — `crc32`, `xor_bytes`, big-endian `u16`/`u32` pack/unpack,
  bit-string conversion helpers.

### Added — Stage 2: Blackhorse Language (`blackhorse/language/`)

- **Custom 256-symbol table** (Table ID 0) — Blackhorse-native encoding,
  not ASCII, not UTF-8. Symbols ordered by English-text frequency:
  - Group A (64 symbols) → 7-bit prefix-free codes (prefix `0`)
  - Group B (64 symbols) → 8-bit prefix-free codes (prefix `10`)
  - Group C (128 symbols) → 9-bit prefix-free codes (prefix `11`)
- **`BHLEncoder`** — encode `str`/`bytes` into a self-describing `BHLPacket`.
- **`BHLDecoder`** — decode a `BHLPacket` back to original bytes or string.
- **`BHLPacket`** — wire format: magic `b'BHL\x1A'` + version + table ID +
  bit-count + bit-packed payload + CRC-32 footer.
- **`docs/BHL_SPEC.md`** — complete language specification (symbol table,
  code assignment algorithm, decoding pseudocode, packet wire format,
  flags, performance characteristics, interoperability requirements).

### Added — Stage 3: Compression Engine (`blackhorse/compression/`)

- **`Compressor`** / **`Decompressor`** — LZ77 compressor operating on
  BHL-encoded bytes with configurable look-behind window (8–16 bits,
  default 4096 bytes). Match encoding: 12-bit offset + 4-bit length in 2 bytes.
  Repetitive data compresses by 50%+.
- Wire format: `b'LZB'` magic + version + window bits + original size + CRC-32.

### Added — Stage 4: Symmetric Encryption (`blackhorse/crypto/symmetric/`)

- **`ChaCha20Cipher`** — RFC 8439 ChaCha20 stream cipher via the
  `cryptography` library. 256-bit key, 96-bit nonce, configurable counter.
  Stateless: `encrypt == decrypt` (XOR stream).

### Added — Stage 5: Asymmetric Key Exchange (`blackhorse/crypto/asymmetric/`)

- **`Curve25519`** / **`KeyPair`** — X25519 ECDH key exchange + HKDF-SHA256
  key derivation via the `cryptography` library. Ephemeral keypair per
  message gives forward secrecy.

### Added — Stage 6: HMAC Signing (`blackhorse/crypto/signing/`)

- **`BHLSigner`** — HMAC-SHA256 authentication tag over a `SignedPacket`
  wire format (`b'BHLS'` magic). `sign()`, `verify_and_extract()`, `verify()`.
  Detects tampering before decryption.

### Added — Stage 7: AI Handshake Interface (`blackhorse/interface/`)

- **`BlackhorseSession`** — single entry point for the full pipeline:
  `pack(message, recipient_pubkey)` → `.bhp` packet bytes;
  `unpack(packet_bytes)` → `(message, metadata)`.
- **Full pipeline**: BHL encode → LZ77 compress → ChaCha20 encrypt
  (ephemeral X25519 ECDH key exchange) → HMAC-SHA256 sign → `.bhp` packet.
- **`.bhp` wire format**: `b'BHP\x1A'` magic + version + timestamp +
  ephemeral sender pubkey (32 B) + nonce (12 B) + payload length + signed payload.
- **Handshake packet** (`b'BHHS'`): session greeting with X25519 pubkey
  + JSON agent info (model, version, timestamp, capabilities).
- `from_handshake()` — parse a peer handshake for key exchange without
  out-of-band coordination.

### Added — Test suite (`tests/`)

- **144 tests, all passing** across all 7 stages:
  - `test_core.py` — 32 tests (BitStream, RingBuffer, utils)
  - `test_language.py` — 26 tests (symbols, packet, encoder, decoder)
  - `test_compression.py` — 14 tests (LZ77 round-trips, edge cases)
  - `test_crypto_symmetric.py` — 14 tests (ChaCha20 encrypt/decrypt)
  - `test_crypto_asymmetric.py` — 14 tests (Curve25519, HKDF)
  - `test_crypto_signing.py` — 15 tests (BHLSigner)
  - `test_interface.py` — 29 tests (full pipeline, handshake)

### Added — Project files

- `requirements.txt` — `cryptography>=41`, `pytest>=7`, `pytest-cov>=4`
- `pyproject.toml` — setuptools build configuration
- `docs/BHL_SPEC.md` — complete BHL specification
- `CHANGELOG.md` — this file

---

## Architecture note on cryptography

The v0.1.0 cryptographic stack uses **classical algorithms**:

| Layer | Algorithm | Security notes |
|-------|-----------|----------------|
| Symmetric encryption | ChaCha20-256 | Quantum-safe (Grover: 128-bit effective) |
| Key exchange | X25519 (Curve25519) | Classical — vulnerable to Shor's algorithm on a CQ machine |
| Key derivation | HKDF-SHA256 | Quantum-safe (Grover: 128-bit effective) |
| Authentication | HMAC-SHA256 | Quantum-safe |
| Encoding | BHL (custom) | Algorithm-agnostic; key exchange is the PQ transition point |

**Post-quantum transition path**: The architecture is designed so that the
X25519 key exchange in Stage 5 can be replaced with a NIST-standardised
post-quantum KEM (e.g. ML-KEM / CRYSTALS-Kyber) with no changes to any
other stage. The Blackhorse Sentinel application uses SHA-3-512 for the
quantum-transition hash in preparation for this upgrade.

---

[0.1.0]: https://github.com/machew15/blackhorse/releases/tag/v0.1.0
