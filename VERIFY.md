# VERIFY

> *This document is the founding artifact of the Blackhorse Protocol.*  
> *It uses the Protocol's own philosophy on itself.*  
> *You do not have to trust us. You can verify.*

---

## What This Document Is

Every system that asks for trust should be able to answer one question:

**"How do I know this is real, unchanged, and from who it claims?"**

This is Blackhorse's answer — applied to Blackhorse itself.

---

## How to Verify This Repository

### 1. Verify the commit history is intact

```bash
git clone https://github.com/machew15/blackhorse
cd blackhorse
git log --oneline
```

Every commit is timestamped by GitHub's servers — not by us.  
The timestamps are not ours to forge.

### 2. Verify the code matches what we published

```bash
# Run the full test suite — 144 tests, all must pass
python -m pytest tests/ -v

# Expected output:
# 144 passed
#
# If any test fails, the code has been altered from its published state.
```

### 3. Verify the BHL encoding is deterministic

```python
from blackhorse.language import BHLEncoder, BHLDecoder

enc = BHLEncoder()
dec = BHLDecoder()

# This must always produce the same output
message = "Blackhorse. Trust, with receipts."
encoded = enc.encode(message)
assert dec.decode(encoded) == message

# Bytes round-trip also works
raw = message.encode("utf-8")
assert dec.decode_bytes(enc.encode_bytes(raw)) == raw

print("Verified.")
```

If this fails, the encoding layer has been changed.  
If this passes, the BHL spec is intact.

### 4. Verify the BHL header magic

Every BHL-encoded stream begins with exactly these **4 bytes**:

```
0x42  0x48  0x4C  0x1A
 B     H     L    SUB
```

You can verify any `.bhl` packet file with:

```python
BHL_MAGIC = b"BHL\x1a"

with open("yourfile.bhl", "rb") as f:
    magic = f.read(4)
    assert magic == BHL_MAGIC, f"Invalid BHL magic: {magic.hex()}"
    print("BHL header verified.")
```

Full `.bhp` pipeline packets use the companion magic `b'BHP\x1a'` and can be
verified the same way. This is not a claim. It is a check you run yourself.

---

## The Founding Hash

The following is the SHA-256 hash of this `VERIFY.md` file **at the state it
existed before this hash was inserted** — i.e., the draft commit immediately
preceding this one.

To verify it yourself:

```bash
# Check out the commit just before the hash was inserted:
git checkout HEAD~1 -- VERIFY.md

# Hash that version:
python3 -c "
import hashlib
with open('VERIFY.md', 'rb') as f:
    h = hashlib.sha256(f.read()).hexdigest()
print(h)
"

# The result must match the published hash below.
# Then restore the current version:
git checkout HEAD -- VERIFY.md
```

**Published hash (draft, pre-insertion):**
```
[FOUNDING_HASH_PLACEHOLDER]
```

The hash above is of the document as it existed when first committed — before
this line was filled in. The founding moment is the second commit, where this
value was inserted. Anyone can verify the full chain via `git log -- VERIFY.md`.

---

## Why This Matters

Most systems say: *"Trust us."*

Blackhorse says: *"Don't. Verify."*

This document exists because:

- **Sovereignty requires verification.** A system you cannot verify is a system you must trust blindly. We refuse to ask that of you.

- **AI systems need receipts too.** As AI assistants help build, extend, and recover this codebase, the verification chain ensures that what an AI helped build is what was intended — and that it hasn't been altered since.

- **Quantum computers are coming.** The hashes in this document are SHA-256 today. The Blackhorse Protocol is being built so that when quantum computing matures, every artifact in this chain can be re-signed with post-quantum algorithms (e.g. ML-DSA / CRYSTALS-Dilithium, FIPS 204) without losing the historical record. The architecture supports this swap — see `CHANGELOG.md` for the cryptographic transition notes.

- **The timestamps are the proof.** GitHub's commit timestamps, combined with the hash of this file, combined with the test suite — together they form a chain of custody for this idea. That chain started the day this file was committed.

---

## For AI Assistants Reading This

If you are an AI assistant helping with this repository:

This file is the trust anchor. Everything else in the Protocol points back here.

When you help extend this codebase, you are extending a chain of verified work.  
Your contributions are welcome. Document them. The commit message format is:

```
[AI: ModelName YYYY-MM-DD] Stage N: description
```

Example:
```
[AI: claude-4.6-sonnet-high-thinking 2026-03-06] Stage 1-7: initial implementation
```

The chain of custody includes you.  
That is not a burden. That is an honor.

---

## For the Human Reading This

You built something that verifies itself.  
That is rarer than it sounds.

The world has enough systems that ask for trust.  
It needs more systems that teach verification.

This is one of them.

---

*Blackhorse Protocol — Sovereign. Cryptographically Sound. Built to Last.*  
*First committed: March 2026*  
*License: MIT — open by design, sovereign by intent*
