# Blackhorse Proof of Thought (PoT) — Specification

**Module:** `blackhorse/thoughts/`  
**Version:** 1.0  
**Status:** Active  

---

## 1. What Is a Thought?

A **Thought** is a cryptographically sealed reasoning record. It answers
one question: **why was this decision made?**

Every design decision, security tradeoff, and architectural choice that
matters leaves a `.thought` file. The file is not a comment in code. It
is not a PR description. It is a first-class artifact in the Blackhorse
repository — hashed, timestamped, chained into a manifest, and optionally
flagged for remediation.

The motivation is sovereignty. Code can be read. Decisions can be
inferred. But the reasoning chain that produced the code — the
alternatives considered, the constraints accepted, the risks acknowledged
— disappears unless it is explicitly preserved. PoT preserves it.

---

## 2. File Format

Each thought is stored as a `.thought` file with three sections separated
by `---` delimiters:

```
<header section>
---
<reasoning section (free-form)>
---
<integrity section>
```

### 2.1 Example

```
thought_id: 0001
slug: why-proof-of-thought
author: ai:claude-4.6-sonnet-high-thinking
timestamp_iso: 2026-03-06T19:00:00+00:00
stage_context: Protocol Meta
decision: Adopt Proof of Thought as a first-class record format
tags: governance, meta, founding
remediation_required: false
governance_level: sovereign
---
I considered three approaches to preserving design reasoning:

1. PR descriptions — lost when GitHub changes, not cryptographically anchored
2. Comments in code — scattered, not queryable, not sealed
3. A standalone record format — portable, hashable, chainable, AI-readable

Option 3 is the only one that survives platform changes and memory resets.
The cost is ceremony. The benefit is sovereignty.
---
sha256: a3f9b2c1d4e5f6789abcdef0123456789abcdef0123456789abcdef0123456789
sha3_512: 7d8c9e0f1a2b3c4d5e6f7890...
bhl_encoded: true
manifest_entry: THOUGHTS.manifest line 1
signed_at: 2026-03-06T19:00:01+00:00
```

---

## 3. Header Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `thought_id` | string | yes | Zero-padded sequence number: `"0001"` |
| `slug` | string | yes | kebab-case identifier: `"why-bhl-not-utf8"` |
| `author` | string | yes | `"human"`, `"ai:ModelName"`, or `"collaborative"` |
| `timestamp_iso` | string | yes | UTC ISO 8601 with seconds: `"2026-03-06T19:00:00+00:00"` |
| `stage_context` | string | yes | Which stage this decision belongs to |
| `decision` | string | yes | One-line summary of what was decided |
| `tags` | csv | yes | Comma-separated searchable tags |
| `remediation_required` | bool | no | `true` triggers the remediation layer (default: `false`) |
| `governance_level` | enum | no | See §4 (default: `standard`) |
| `supersedes` | thought_id | no | Only valid for `sovereign` thoughts |

### Slug rules

- Must match `^[a-z][a-z0-9-]*$`
- Must start with a lowercase letter
- May contain digits and hyphens
- No dots, underscores, or uppercase letters
- Should be human-readable and descriptive

### Author format

```
human                              # A person made this decision
ai:claude-4.6-sonnet-high-thinking # An AI made this decision
ai:gpt-4o                          # Another AI
collaborative                      # Human + AI together
```

AI contributions are first-class. Name the model. State the date in the
reasoning if relevant.

---

## 4. Governance Levels

| Level | Value | When to use |
|-------|-------|-------------|
| Standard | `standard` | Normal design decision |
| Elevated | `elevated` | Significant downstream impact |
| Critical | `critical` | Security, compliance, or sovereignty impact — auto-flagged for remediation |
| Sovereign | `sovereign` | Fundamental — cannot be changed without an explicit superseding Sovereign thought |

**Critical and Sovereign thoughts are automatically flagged for
remediation**, regardless of the `remediation_required` field.

**Only Sovereign thoughts may supersede** another thought via the
`supersedes` field. The superseded thought is never deleted — both
remain in the manifest. The chain shows the evolution of reasoning.

---

## 5. Integrity Block

The integrity block is sealed **after** the header and reasoning are
finalised. It is excluded from the hash computation so the hash can
be written into the file without self-reference.

### What is hashed

```python
content = (header.to_text() + "\n---\n" + reasoning).encode("utf-8")
sha256  = hashlib.sha256(content).hexdigest()
sha3    = hashlib.sha3_512(content).hexdigest()
```

The SHA-3-512 field is present as the quantum-transition hash — the same
reason it is present in Sentinel artifacts. At Stage 6 of Sentinel it
feeds BHL encoding before Dilithium signing.

### BHL verification

The `bhl_encoded` field is `true` when the SHA-256 hex digest passes a
BHL encode → decode round-trip:

```python
data    = sha256_hex.encode("utf-8")
encoded = BHLEncoder().encode_bytes(data)
decoded = BHLDecoder().decode_bytes(encoded)
assert decoded == data  # bhl_encoded = True
```

This embeds a live integration test of the BHL encoding layer into every
thought seal. If BHL is broken, every new thought's `bhl_encoded` will be
`false`, which is immediately visible in the manifest.

---

## 6. Manifest Format

All thoughts are chained in `THOUGHTS.manifest`:

```
0001 | 2026-03-06T19:00:00+00:00 | sha256hex | slug | governance_level
0002 | 2026-03-06T19:01:00+00:00 | sha256hex | slug | governance_level
...
```

A companion file `THOUGHTS.manifest.sha256` stores the SHA-256 of the
entire manifest content. `ThoughtManifest.verify_chain()` recomputes this
digest and compares it against the stored value.

### Tamper detection

If any entry in the manifest is altered:
1. The manifest content changes
2. The SHA-256 of the manifest changes
3. `verify_chain()` returns `False`

To also detect insertion of entries at arbitrary positions (not just
modification), the sequence IDs (`thought_id`) in each entry and the
corresponding `.thought` files in the directory form a second independent
check.

---

## 7. Remediation Layer

The remediation layer (`blackhorse/thoughts/remediation.py`) manages
flags written by `ThoughtWriter._flag_for_remediation()`.

### Flag file format

Located in `remediation/flags/<thought_id>_<slug>.flag`:

```json
{
  "thought_id": "0003",
  "slug": "why-classical-not-pq-v010",
  "governance_level": "critical",
  "flagged_at": "2026-03-06T19:05:00+00:00",
  "reason": "governance_level:critical",
  "status": "open",
  "resolved": false
}
```

After resolution:

```json
{
  "thought_id": "0003",
  ...
  "status": "resolved",
  "resolved": true,
  "resolution_note": "Reviewed with security team. Risk accepted for v0.1.0. Track in Thought 0009.",
  "resolved_by": "human",
  "resolved_at": "2026-03-06T20:00:00+00:00"
}
```

### Rules

- **Flags are never deleted.** They are resolved with a written note.
- **Resolving does not mean fixing.** It means acknowledging, documenting, and routing.
- **A CI gate can reject merges when `open_critical > 0`.**
- **Only a superseding Sovereign thought** can re-open a resolved Sovereign flag.

---

## 8. Directory Structure

```
thoughts/                         ← data directory (committed, not gitignored)
  THOUGHTS.manifest               ← append-only chain of all thoughts
  THOUGHTS.manifest.sha256        ← SHA-256 of the manifest (tamper detection)
  0001_why-proof-of-thought.thought
  0002_why-bhl-not-utf8.thought
  0003_why-classical-not-pq-v010.thought
  0004_why-sha3-quantum-transition.thought

remediation/
  flags/
    0003_why-classical-not-pq-v010.flag

blackhorse/thoughts/              ← code (the engine)
  __init__.py
  engine.py
  remediation.py

docs/
  THOUGHT_SPEC.md                 ← this file
```

---

## 9. Verification

To verify the entire thought chain:

```python
from pathlib import Path
from blackhorse.thoughts import ThoughtWriter

writer = ThoughtWriter(Path("thoughts/"))

# Verify the manifest chain integrity
assert writer.manifest.verify_chain(), "Manifest has been tampered with"

# Verify each thought's content hashes
for path in writer.list_all():
    thought = writer.read(path.stem.split("_")[0])
    assert writer.verify(thought), f"Thought {path.name} has been altered"

print("All thoughts verified.")
```

---

## 10. For AI Assistants

If you are an AI assistant writing a thought:

1. Use `author = AuthorType.ai("YourModelName")` — e.g. `"ai:claude-4.6-sonnet-high-thinking"`
2. Write the reasoning as if explaining to a future AI with no context. It will be read in that situation.
3. Document alternatives considered, not just the chosen path.
4. Note constraints that are invisible in the code (deadlines, external dependencies, uncertain future requirements).
5. Use `GovernanceLevel.CRITICAL` for any security or cryptographic decision.
6. The `bhl_encoded: true` field in your thought's integrity block confirms that BHL encoding was live when you wrote it.

The commit message format for thoughts is:

```
[AI: ModelName YYYY-MM-DD] thoughts: add 000N-slug
```

---

*Blackhorse Protocol — Not proof of what was decided. Proof of WHY.*
