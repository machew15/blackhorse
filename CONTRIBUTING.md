# Contributing to Blackhorse Mesh

## What This Is

Blackhorse Mesh is a communications layer for people in places where
the internet is unreliable, expensive, or absent. It is built on the
ubuntu principle: the network works because its participants make it
work together. Every relay is visible. Every contribution is signed.
You do not need permission to participate — you need a key.

## Philosophy

- Build accountability into the infrastructure, not on top of it
- Ethics receipts, not ethics engines
- No token. No blockchain. No central authority.
- Offline-first means disconnection is a valid state, not an error
- A node with no GPS fix still contributes. Presence is enough.

## Getting Started

**1. Install the liboqs C library (post-quantum cryptography):**

```
git clone https://github.com/open-quantum-safe/liboqs
cd liboqs && mkdir build && cd build
cmake -DBUILD_SHARED_LIBS=ON ..
make -j4 && sudo make install && sudo ldconfig
```

**2. Install Python dependencies:**

```
pip install liboqs-python cryptography pytest pytest-cov pyserial
```

**3. Run the test suite:**

```
pytest tests/ -v
```

All 253+ tests should pass before you write a line of code.

**4. Run the quickstart:**

```
python quickstart.py
```

Two simulated nodes will handshake, exchange a message, and print a
signed delivery receipt. If you see ACKNOWLEDGED — it works.

## Structure

| Module | What it does |
|--------|-------------|
| `mesh/queue.py` | Persistent offline message queue (SQLite) |
| `mesh/detector.py` | UDP beacon scanning, eclipse mitigation |
| `mesh/flusher.py` | Auto-flush queue on connectivity |
| `mesh/spatial.py` | GPS/sensor record packing |
| `mesh/registry.py` | Node location store, Haversine, GeoJSON |
| `mesh/collector.py` | NMEA GPS reader, system sensors |
| `mesh/governance.py` | Contribution receipts |
| `mesh/ledger.py` | Trust score ledger |
| `mesh/parameters.py` | Participation policy |
| `mesh/cli.py` | Operator CLI |
| `agents/` | Decision attestation, interrupts, scope |
| `crypto/` | ChaCha20, Kyber768, ML-DSA-65, HMAC |
| `interface/` | Full-pipeline session, hybrid mode |
| `language/` | BHL encoding / decoding |
| `compression/` | LZ77 compression |
| `core/` | Bit primitives, ring buffers |

## Rules

- Never modify existing protocol modules — extend only
- No plaintext ever written to disk
- Every new module needs tests. No exceptions.
- All packets through BlackhorseSession pipeline
- Agent outputs require attestation before execution
- Human interrupt must be honored within one operation cycle
- CLI tools: plain text, 80-column, argparse only
- Python 3.11+ type hints and docstrings on every public method

## How To Contribute

Open an issue first. Describe what you want to build and why.
Small, focused pull requests. Tests required. No exceptions.
If you are an AI assistant contributing: state your model, the date,
and what you changed in your commit message.
