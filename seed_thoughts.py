"""
Seed the founding thought records for the Blackhorse Protocol.

Run once: python seed_thoughts.py
These records are committed to the repository alongside code.
"""

from pathlib import Path
from blackhorse.thoughts import ThoughtWriter, GovernanceLevel, AuthorType

writer = ThoughtWriter(Path("thoughts/"))

# ─────────────────────────────────────────────
# 0001 — Why Proof of Thought itself
# ─────────────────────────────────────────────
writer.create(
    slug="why-proof-of-thought",
    author=AuthorType.ai("claude-4.6-sonnet-high-thinking"),
    stage_context="Protocol Meta",
    decision="Adopt Proof of Thought as a first-class, cryptographically-sealed record format for all significant design decisions",
    governance_level=GovernanceLevel.SOVEREIGN,
    tags=["governance", "meta", "founding", "sovereignty"],
    reasoning="""
I considered three approaches to preserving the reasoning behind design decisions:

OPTION A — PR descriptions and commit messages
  Pros: Zero ceremony, already happens
  Cons: Lost when GitHub changes or account issues arise; not independently
  verifiable; not searchable by governance level; gives no record of
  alternatives considered; disappears from context across AI sessions

OPTION B — Inline code comments
  Pros: Close to the code that implements the decision
  Cons: Scattered; not queryable; not sealed; get deleted when code
  changes; don't survive major refactors; no structured metadata

OPTION C — A standalone record format
  Pros: Portable, hashable, chainable, AI-readable across session resets;
  carries structured metadata (governance level, tags, supersession);
  can be cryptographically verified; survives platform changes
  Cons: Ceremony cost; must discipline to actually write them

The Blackhorse Protocol is explicitly designed for sovereignty under
adversarial conditions (platform changes, memory resets, account issues).
A governance system that doesn't survive those conditions offers only the
illusion of governance.

Option C is the only one that is actually sovereign. The ceremony cost is
the price of a record that lasts. Given that this is a protocol designed
to outlast any single platform or AI session, that price is correct.

The Proof of Thought system is itself designed using the reasoning it
was designed to preserve. This recursion is intentional.
""".strip(),
)

# ─────────────────────────────────────────────
# 0002 — Why BHL uses a custom symbol table
# ─────────────────────────────────────────────
writer.create(
    slug="why-bhl-not-utf8",
    author=AuthorType.ai("claude-4.6-sonnet-high-thinking"),
    stage_context="Protocol Stage 2 — Blackhorse Language",
    decision="BHL uses a Blackhorse-native symbol table ordered by English-text frequency, not UTF-8 or ASCII",
    governance_level=GovernanceLevel.ELEVATED,
    tags=["encoding", "bhl", "design", "stage-2"],
    reasoning="""
The question was whether BHL should be a thin wrapper around an existing
encoding (UTF-8, ASCII, or a standard Huffman table) or define its own
symbol ordering.

OPTION A — Wrap UTF-8 verbatim
  Pros: Zero cognitive overhead for ASCII text; everyone understands UTF-8
  Cons: UTF-8 is a variable-width Unicode encoding designed for
  interoperability, not for bit-packing efficiency or frequency-optimised
  compression. It encodes common ASCII in 8 bits, which is the ceiling
  of what BHL achieves for its 7-bit group. No benefit over raw bytes.

OPTION B — Use a standard Huffman table (e.g. from DEFLATE / zlib)
  Pros: Well-studied; tools exist
  Cons: DEFLATE's symbol tables are computed per-stream from the data,
  not static. Static Huffman tables from reference implementations are
  not designed for BHL's specific 3-group (7/8/9-bit) structure. Using
  one would require either adapting it awkwardly or accepting sub-optimal
  bit savings.

OPTION C — Blackhorse-native frequency ordering
  Pros: Designed specifically for the 3-group code structure; optimised
  for English text + source code (the primary BHL use cases); the
  symbol ordering IS the spec — it's reproducible, versionable, and
  self-contained; it makes BHL genuinely "Blackhorse-native" as designed
  Cons: Not interoperable with other encodings; requires the BHL spec to
  decode (which is the point — sovereignty requires the spec)

The key insight: BHL is not a wire format for interoperability. It is a
sovereign encoding layer whose symbol table IS part of the protocol
specification. Making it "not UTF-8, not ASCII" is not stubbornness —
it is the mechanism that makes BHL-encoded data require the Blackhorse
spec to decode, which is exactly the sovereignty guarantee the protocol
is designed to provide.

Common English characters (space, e, t, a, o, i, n, s) get 7-bit codes.
Rare bytes (high-value bytes 0x8C–0xFF) get 9-bit codes. The table is
static, deterministic, and ships as a constant in symbols.py.
""".strip(),
)

# ─────────────────────────────────────────────
# 0003 — Why Curve25519 (not CRYSTALS-Kyber) for v0.1.0
# ─────────────────────────────────────────────
writer.create(
    slug="why-classical-not-pq-v010",
    author=AuthorType.ai("claude-4.6-sonnet-high-thinking"),
    stage_context="Protocol Stage 5 — Asymmetric Cryptography",
    decision="Use X25519 (Curve25519 ECDH) for v0.1.0 key exchange instead of a post-quantum KEM",
    governance_level=GovernanceLevel.CRITICAL,
    tags=["crypto", "post-quantum", "curve25519", "security", "stage-5"],
    remediation_required=True,
    reasoning="""
This is the most consequential cryptographic decision in v0.1.0 and it
is deliberately conservative. Here is the full reasoning.

WHAT WE CONSIDERED
------------------
Option A: X25519 (Curve25519) via the `cryptography` library
  - Widely deployed, battle-tested, audited, deterministic
  - Vulnerable to Shor's algorithm on a sufficiently powerful quantum computer
  - Forward secrecy via ephemeral keypairs per message

Option B: ML-KEM (CRYSTALS-Kyber, FIPS 203) — the NIST-standardised PQ KEM
  - Genuinely post-quantum
  - The `pqcrypto` and `kyber-py` libraries exist but are not production-audited
    to the same standard as the `cryptography` library's X25519 implementation
  - Kyber key generation and encapsulation parameters are more complex
    to implement correctly

Option C: Hybrid (X25519 + ML-KEM in parallel)
  - The gold standard for the transition period
  - Doubles the key material overhead
  - Correct approach for production systems but introduces complexity
    that v0.1.0 is not ready to carry without audited PQ library support

WHY WE CHOSE OPTION A FOR v0.1.0
---------------------------------
1. The `cryptography` library's X25519 is production-audited and deployed
   at scale. The PQ alternatives available in Python are not yet at
   comparable audit depth.

2. Cryptographic mistakes compound. A poorly-implemented Kyber is worse
   than a correctly-implemented X25519 that acknowledges its quantum
   limitation honestly.

3. The architecture is explicitly designed for the swap. The key exchange
   in Stage 5 is isolated behind a single class (Curve25519 / KeyPair).
   Replacing it with ML-KEM requires changing one file. The pipeline
   (Stage 7: BlackhorseSession) doesn't change at all.

4. SHA-3-512 is used as the quantum-transition hash in Sentinel artifacts
   (it is Grover-resistant at 256-bit effective security). This means
   the hash chain survives the quantum transition even before the key
   exchange does.

THE RISK WE ARE ACCEPTING
-------------------------
Any Blackhorse Packet (.bhp) encrypted with X25519 today could, in
principle, be decrypted by a sufficiently powerful quantum computer
in the future via "harvest now, decrypt later."

This risk is accepted for v0.1.0 because:
- No production user data is at risk (this is an early-stage open protocol)
- The architectural swap path is built and documented
- The timeline for harvest-now-decrypt-later attacks on 256-bit ECDH
  to be practically feasible is measured in years, not months

REMEDIATION PATH
----------------
Stage 6 of Sentinel (BHL + Dilithium signing) should be coupled with a
v0.2.0 Protocol release that introduces hybrid X25519+ML-KEM key exchange.
Track this in a new Sovereign thought when that work begins.

HONEST DISCLOSURE
-----------------
This protocol should not be advertised as "post-quantum safe" based on
v0.1.0. The CHANGELOG.md and architecture documentation reflect this.
""".strip(),
)

# ─────────────────────────────────────────────
# 0004 — Why SHA-3-512 as the quantum-transition hash
# ─────────────────────────────────────────────
writer.create(
    slug="why-sha3-quantum-transition",
    author=AuthorType.ai("claude-4.6-sonnet-high-thinking"),
    stage_context="Protocol Stage 6 prep / Sentinel Stage 1",
    decision="Use SHA-3-512 as the quantum-transition hash alongside SHA-256, preserved specifically for BHL encoding at Stage 6",
    governance_level=GovernanceLevel.ELEVATED,
    tags=["crypto", "hashing", "sha3", "post-quantum", "sentinel", "stage-6-prep"],
    reasoning="""
Every artifact in Blackhorse Sentinel gets two hashes: SHA-256 and SHA-3-512.
The SHA-256 is for present-day compatibility. The SHA-3-512 is a deliberate
architectural choice for the post-quantum transition. Here is why.

WHY TWO HASHES AT ALL
---------------------
Single-hash systems create a cliff. When SHA-256 becomes computationally
weakened (Grover's algorithm gives a quantum computer an effective
√2^256 = 2^128 attack against SHA-256 preimage resistance), every
artifact in the system must be re-hashed if there is only one digest.

With two hashes from the start, the SHA-3-512 digest is already present
for every artifact. The transition is additive, not substitutive.

WHY SHA-3 SPECIFICALLY
----------------------
SHA-3 (Keccak) is based on a sponge construction, which is structurally
different from SHA-2's Merkle-Damgård construction. This matters because:

1. A structural weakness in SHA-2 (like the length extension attack, which
   HMAC mitigates but which SHA-3 doesn't have) doesn't transfer to SHA-3.

2. SHA-3 is NIST-standardised (FIPS 202, 2015). It's not a boutique
   construction — it's an internationally reviewed standard.

3. SHA-3-512 at 512 bits gives 256-bit Grover-resistant preimage
   resistance. This is the quantum-safe threshold for symmetric
   primitives under conservative estimates.

WHY 512 BITS (NOT SHA-3-256)
----------------------------
SHA-3-256 gives 128-bit quantum resistance (half of 256). SHA-3-512
gives 256-bit quantum resistance. For long-lived artifacts (documents
that should be verifiable in 20–30 years), 256-bit post-quantum margin
is the right call. The storage cost (128 hex chars vs 64) is trivial.

THE BHL CONNECTION
------------------
At Protocol Stage 6, the SHA-3-512 digest is BHL-encoded before being
passed to the signing layer. BHL encoding at 7-bit average codes for
hex characters (all in the [0-9a-f] range, which are common ASCII
characters in the 7-bit BHL group) means the encoded form is more
compact than raw bytes and is wrapped in a self-describing packet.

This creates a chain:
  artifact bytes → SHA-3-512 → BHL encode → Dilithium sign
where each layer adds a layer of verifiable structure. The BHL
encoding is not just compression — it marks the hash as having passed
through the Blackhorse encoding layer, which is part of the Protocol's
chain of custody.

DECISION
--------
SHA-3-512 is stored in every artifact record from Stage 1 forward,
even though Stage 6 integration hasn't happened yet. This is deliberate.
Retrofitting 512-bit hashes onto historical artifacts retroactively
requires re-hashing them, which is operationally complex and breaks
timestamp proofs. Having the hash from day one eliminates this problem.
""".strip(),
)

print("Founding thoughts created:")
for path in writer.list_all():
    print(f"  {path.name}")
print(f"\nManifest chain verified: {writer.manifest.verify_chain()}")
print(f"BHL encoded on all: {all(writer.verify(writer.read(str(i+1).zfill(4))) for i in range(4))}")
