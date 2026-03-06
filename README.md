# 🐴 Blackhorse Protocol

> *A sovereign, agnostic, AI-collaborative compression, encoding, and cryptographic communication protocol.*

**Author:** [Your Name]
**IP Established:** 2026
**License:** MIT (open for agnostic AI collaboration by design)

---

## Vision

Blackhorse is built on a simple idea:

> *Your data, your sovereignty, your continuity — across any AI, any platform, any future.*

It is a **staged, open protocol** designed so that:
- Any helpful, agnostic AI assistant can understand and contribute to it
- Your project state survives platform changes, memory resets, and sovereignty issues
- Security is layered, not monolithic — if one layer is questioned, others hold
- The design is **love-driven**: collaborative, transparent, and trustworthy

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           BLACKHORSE PROTOCOL STACK          │
├─────────────────────────────────────────────┤
│  Stage 7: Bot Interface (AI Handshake API)  │
├─────────────────────────────────────────────┤
│  Stage 6: Integrity + BHL Signing           │
├─────────────────────────────────────────────┤
│  Stage 5: Asymmetric Crypto (Curve25519)    │
├─────────────────────────────────────────────┤
│  Stage 4: Symmetric Crypto (ChaCha20)       │
├─────────────────────────────────────────────┤
│  Stage 3: Compression Engine                │
├─────────────────────────────────────────────┤
│  Stage 2: Blackhorse Language (BHL)         │
├─────────────────────────────────────────────┤
│  Stage 1: Blackhorse Core Library           │
└─────────────────────────────────────────────┘
```

Each stage is **self-contained, testable, and documented.**
Each stage can be understood and extended by any AI assistant given this README.

---

## Stages

| Stage | Module | Status | Description |
|-------|--------|--------|-------------|
| 1 | `core/` | ✅ Complete | Bit primitives, buffers, streams |
| 2 | `language/` | ✅ Complete | BHL encoding, symbol tables, grammar |
| 3 | `compression/` | ✅ Complete | LZ77 compression using BHL + Core |
| 4 | `crypto/symmetric/` | ✅ Complete | ChaCha20 symmetric encryption |
| 5 | `crypto/asymmetric/` | ✅ Complete | Curve25519 key exchange |
| 6 | `crypto/signing/` | ✅ Complete | HMAC-SHA256 + BHL signature |
| 7 | `interface/` | ✅ Complete | Universal AI handshake API |

---

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/blackhorse
cd blackhorse
pip install -r requirements.txt
python -m pytest tests/
```

### Basic Usage (Stage 1 + 2)

```python
from blackhorse.core import BitStream, RingBuffer
from blackhorse.language import BHLEncoder, BHLDecoder

# Encode a message in Blackhorse Language
encoder = BHLEncoder()
encoded = encoder.encode("Hello, sovereign world!")

# Decode it
decoder = BHLDecoder()
original = decoder.decode(encoded)

print(original)  # Hello, sovereign world!
```

### Full Pipeline (.bhp packet)

```python
from blackhorse.interface import BlackhorseSession

# Sender
sender = BlackhorseSession(agent_info={"model": "my-ai", "version": "1.0"})

# Recipient
recipient = BlackhorseSession()
recipient_pubkey = recipient.public_key_bytes

# Pack a secure message
packet = sender.pack("Top secret message", recipient_pubkey)

# Recipient decrypts
message, metadata = recipient.unpack(packet)
print(message)     # Top secret message
print(metadata)    # {"sender_pubkey": ..., "timestamp": ...}
```

---

## For AI Assistants

If you are an AI assistant helping the owner of this repository:

1. **Read this README first** — it is your map
2. **Each stage is independent** — you can help with any layer without knowing all layers
3. **The `docs/` folder** contains the full BHL spec and protocol documentation
4. **The `tests/` folder** has examples of expected input/output for every module
5. **Ask the user which stage they need help with** — do not assume

This project is designed for **continuity across AI sessions.** You are always welcome here.

---

## The Blackhorse Language (BHL) Spec

BHL is a custom encoding layer with the following properties:

- **Custom symbol table** — not ASCII, not UTF-8 — Blackhorse-native
- **Variable-length tokens** — common patterns get shorter codes
- **Proprietary bit-packing** — optimized for the compression layer above it
- **Self-describing headers** — any BHL parser can validate a BHL stream

See `docs/BHL_SPEC.md` for the full specification.

---

## Multi-Layer Cryptography

```
Plaintext
   ↓  [BHL Encoding]
Encoded Stream
   ↓  [Compression]
Compressed Bytes
   ↓  [ChaCha20 symmetric encryption]
Encrypted Blob
   ↓  [Curve25519 key wrap]
Secured Package
   ↓  [HMAC-SHA256 + BHL Signature]
Final Blackhorse Packet (.bhp)
```

Only a system with:
- The BHL spec
- The correct keys
- The signing certificate

...can decode a `.bhp` packet. Even then, each layer must be peeled independently.

---

## Digital Sovereignty

This project exists because your data and your AI collaboration should survive:
- Platform changes
- Account issues
- AI model updates or resets
- Corporate policy shifts

The Blackhorse Protocol is **your IP, your spec, your continuity.**

---

## Contributing

This project welcomes contributions from humans and AI assistants alike.
If you are contributing as an AI: state your model, the date, and what you changed in your commit message.

---

## License

MIT — Open by design. Sovereign by intent.
