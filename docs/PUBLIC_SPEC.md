# Blackhorse Mesh — Public Specification

**Version:** 1.0
**Status:** Draft
**Protocol:** Blackhorse Mesh v1

---

## Governance Principle: Ubuntu

The Blackhorse Mesh is governed by the ubuntu principle:
*"I am because we are."*

No node on the network is more important than the network itself. Trust is not
assigned by any central authority — it is earned through observable, verifiable
contribution. A node that reliably relays messages for others is rewarded with
higher trust and broader participation rights. A node that repeatedly fails,
withholds capacity, or tampers with packets loses trust and is gradually excluded
from relay paths.

Governance parameters — such as minimum trust thresholds, quorum requirements,
and relay limits — are set collectively. No single node can unilaterally change
the rules. Changes require a quorum of participating nodes to agree, and all
decisions are recorded in a tamper-evident local ledger.

---

## ContributionReceipt

Every successful message relay produces a `ContributionReceipt`. Receipts are the
primary unit of trust accounting on the mesh. They are cryptographically signed
and cannot be forged or replayed.

| Field | Description |
|-------|-------------|
| `receipt_id` | Unique identifier for this receipt (UUID) |
| `message_id` | The message this receipt corresponds to |
| `contributor_id` | Node identifier of the node that performed the relay |
| `action_type` | The type of contribution: `RELAY`, `STORE`, or `VALIDATE` |
| `weight` | Numeric contribution weight assigned by the network policy |
| `timestamp` | UTC datetime when the contribution was recorded |
| `relay_node_id` | Identifier of the relay node that issued the receipt |
| `signature` | HMAC-SHA256 signature verifying the receipt's authenticity |

Receipts are stored locally by the contributing node and presented as evidence
during trust score calculations. A receipt is valid for a configurable TTL after
which it no longer contributes to the active trust score.

---

## Trust Score Methodology

Each node on the mesh maintains a trust score calculated from its accumulated
`ContributionReceipt` records. The methodology is intentionally simple and auditable.

**How trust is earned:**
A node earns trust by successfully relaying messages on behalf of others. Each
`ContributionReceipt` carries a weight, and higher-weight receipts (such as those
for critical-priority messages or long-distance relays) contribute proportionally
more to the trust score.

**How trust is lost:**
Failed delivery attempts, timeouts, and unacknowledged packets reduce the score.
The reduction is proportional to the expected contribution weight that was not
delivered.

**Time decay:**
Trust scores decay gradually over time if a node is inactive. This prevents
nodes from accumulating trust historically and then behaving badly. Scores are
re-evaluated on every participation cycle.

**Minimum threshold:**
A minimum trust score is required to participate as a relay node. Nodes below the
threshold may still send messages but cannot relay for others until their score
recovers.

---

## ParticipationPolicy Parameters

The `ParticipationPolicy` defines the rules under which nodes participate in the
mesh. These parameters are agreed upon by a quorum of nodes and stored in the
distributed governance ledger.

| Parameter | Description |
|-----------|-------------|
| `min_trust_score` | Minimum trust score required to act as a relay node |
| `max_relay_hops` | Maximum number of hops a packet may travel before being dropped |
| `scan_interval_seconds` | How often nodes scan for peers on the local network interface |
| `quorum_threshold` | Fraction of known nodes (0.0–1.0) required to approve a policy change |
| `receipt_ttl_seconds` | How long a ContributionReceipt remains valid for trust accounting |
| `retry_limit` | Maximum number of delivery attempts before a message is marked FAILED |
| `flush_timeout_seconds` | Maximum time to wait for a delivery acknowledgement per packet |

---

## GeoJSON Export

The spatial layer of Blackhorse Mesh maintains a registry of known node locations
and the connections between them. This registry can be exported as a standard
GeoJSON FeatureCollection for use in mapping tools, community dashboards, or
offline geographic analysis.

**The export contains:**
- Each known node as a GeoJSON `Point` feature, with properties including
  `node_id`, `last_seen`, `trust_score`, and `is_reachable`.
- Each active relay connection as a GeoJSON `LineString` feature, with properties
  including `from_node`, `to_node`, `signal_strength`, and `last_relay_timestamp`.

The export is read-only and contains no private keys, message content, or user
identifiers. It is safe to share with community administrators for network
planning and coverage analysis.

---

*Blackhorse Mesh — your network, your community, your continuity.*
