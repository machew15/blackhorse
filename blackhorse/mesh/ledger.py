"""
Phase 3B — Contribution Ledger.

SQLite-backed store of ContributionReceipt records. Computes trust scores
for each node based on verified contributions, recency weighting, and
consistency over time.

Trust score formula (see get_trust_score docstring for full detail):
  base      = verified_count / total_count
  recency   = 2× weight for last-7-day contributions
  consistency = 1.1× multiplier if active > 30 days
  result    = min(1.0, combined_score)
  unknown   = 0.0 for nodes with no records
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Sequence

from .governance import ContributionReceipt


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS contributions (
    receipt_id      TEXT PRIMARY KEY,
    relay_node_id   TEXT NOT NULL,
    origin_node_id  TEXT NOT NULL,
    message_id      TEXT NOT NULL,
    packet_hash     TEXT NOT NULL,
    relay_timestamp TEXT NOT NULL,
    bytes_relayed   INTEGER NOT NULL DEFAULT 0,
    spatial_context TEXT NOT NULL DEFAULT 'unknown',
    direction       TEXT NOT NULL,
    verified        INTEGER NOT NULL DEFAULT 1
);
"""

_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_relay_node ON contributions (relay_node_id);",
    "CREATE INDEX IF NOT EXISTS idx_origin_node ON contributions (origin_node_id);",
    "CREATE INDEX IF NOT EXISTS idx_timestamp ON contributions (relay_timestamp);",
]


# ---------------------------------------------------------------------------
# ContributionLedger
# ---------------------------------------------------------------------------

class ContributionLedger:
    """
    SQLite store for ContributionReceipt records and trust score computation.

    Parameters
    ----------
    storage_path : Filesystem path to the SQLite database file.
    """

    def __init__(self, storage_path: str) -> None:
        self._db_path = storage_path
        self._conn = sqlite3.connect(storage_path, check_same_thread=False)
        self._conn.isolation_level = None
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_CREATE_TABLE)
        for idx in _INDICES:
            self._conn.execute(idx)

    # ------------------------------------------------------------------
    # Record
    # ------------------------------------------------------------------

    def record(
        self,
        receipt: ContributionReceipt,
        direction: str,
        verified: bool = True,
    ) -> None:
        """
        Store a ContributionReceipt in the ledger.

        Parameters
        ----------
        receipt   : The ContributionReceipt to record.
        direction : "GIVEN" (this node relayed) or "RECEIVED" (this node benefited).
        verified  : True if the receipt signature was successfully verified.
        """
        if direction not in ("GIVEN", "RECEIVED"):
            raise ValueError(f"direction must be 'GIVEN' or 'RECEIVED', got {direction!r}")

        self._conn.execute(
            """
            INSERT OR IGNORE INTO contributions
                (receipt_id, relay_node_id, origin_node_id, message_id,
                 packet_hash, relay_timestamp, bytes_relayed, spatial_context,
                 direction, verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.receipt_id,
                receipt.relay_node_id,
                receipt.origin_node_id,
                receipt.message_id,
                receipt.packet_hash,
                receipt.relay_timestamp.isoformat(),
                receipt.bytes_relayed,
                receipt.spatial_context,
                direction,
                1 if verified else 0,
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_node_contributions(self, node_id: str) -> dict:
        """
        Return a contribution summary for a node.

        Counts receipts where the node appears as relay_node_id OR origin_node_id.

        Parameters
        ----------
        node_id : The node to summarise.

        Returns
        -------
        dict
            Keys: given, received, bytes_given, bytes_received, first_seen,
            last_seen (ISO strings or None), total.
        """
        given_row = self._conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(bytes_relayed), 0),
                   MIN(relay_timestamp), MAX(relay_timestamp)
            FROM contributions
            WHERE relay_node_id = ? AND direction = 'GIVEN'
            """,
            (node_id,),
        ).fetchone()

        recv_row = self._conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(bytes_relayed), 0)
            FROM contributions
            WHERE origin_node_id = ? AND direction = 'RECEIVED'
            """,
            (node_id,),
        ).fetchone()

        given = given_row[0] if given_row else 0
        bytes_given = given_row[1] if given_row else 0
        first_seen = given_row[2] if given_row else None
        last_seen = given_row[3] if given_row else None
        received = recv_row[0] if recv_row else 0
        bytes_received = recv_row[1] if recv_row else 0

        return {
            "node_id": node_id,
            "given": given,
            "received": received,
            "bytes_given": bytes_given,
            "bytes_received": bytes_received,
            "first_seen": first_seen,
            "last_seen": last_seen,
            "total": given + received,
        }

    def get_trust_score(self, node_id: str) -> float:
        """
        Compute a trust score in [0.0, 1.0] for a node.

        Algorithm
        ---------
        1. If no contributions recorded → 0.0
        2. base_score = verified_count / total_count
        3. Recency boost: contributions in the last 7 days count 2×
           recency_score = (recent_verified * 2 + old_verified) / (recent_total * 2 + old_total)
           (use recency_score if it improves over base_score)
        4. Consistency multiplier: 1.1× if first contribution > 30 days ago
        5. Result = min(1.0, score)

        Parameters
        ----------
        node_id : The node to score.

        Returns
        -------
        float
            Trust score in [0.0, 1.0]. Unknown nodes score 0.0.
        """
        rows = self._conn.execute(
            """
            SELECT relay_timestamp, verified
            FROM contributions
            WHERE relay_node_id = ?
            """,
            (node_id,),
        ).fetchall()

        if not rows:
            return 0.0

        now = datetime.now(timezone.utc)
        cutoff_recent = now - timedelta(days=7)
        cutoff_old = now - timedelta(days=30)

        total = len(rows)
        verified_total = 0
        recent_total = 0
        recent_verified = 0
        oldest: datetime | None = None

        for ts_str, is_verified in rows:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if is_verified:
                verified_total += 1
            if ts >= cutoff_recent:
                recent_total += 1
                if is_verified:
                    recent_verified += 1
            if oldest is None or ts < oldest:
                oldest = ts

        base_score = verified_total / total

        # Recency-weighted score
        old_total = total - recent_total
        old_verified = verified_total - recent_verified
        weighted_denom = recent_total * 2 + old_total
        if weighted_denom > 0:
            recency_score = (recent_verified * 2 + old_verified) / weighted_denom
        else:
            recency_score = base_score

        score = max(base_score, recency_score)

        # Consistency multiplier: active more than 30 days
        if oldest is not None and (now - oldest) > timedelta(days=30):
            score = min(1.0, score * 1.1)

        return min(1.0, score)

    def top_contributors(self, limit: int = 10) -> list[dict]:
        """
        Return the top contributors ranked by number of verified relays given.

        Parameters
        ----------
        limit : Maximum number of results to return.

        Returns
        -------
        list[dict]
            Each dict has node_id, given, bytes_given, trust_score.
        """
        rows = self._conn.execute(
            """
            SELECT relay_node_id, COUNT(*) AS cnt,
                   COALESCE(SUM(bytes_relayed), 0) AS total_bytes
            FROM contributions
            WHERE direction = 'GIVEN' AND verified = 1
            GROUP BY relay_node_id
            ORDER BY cnt DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            {
                "node_id": row[0],
                "given": row[1],
                "bytes_given": row[2],
                "trust_score": self.get_trust_score(row[0]),
            }
            for row in rows
        ]

    def export_report(self) -> str:
        """
        Generate a human-readable plain-text report of network health.

        Returns
        -------
        str
            An 80-column plain-text report.
        """
        total_row = self._conn.execute("SELECT COUNT(*) FROM contributions").fetchone()
        total = total_row[0] if total_row else 0

        verified_row = self._conn.execute(
            "SELECT COUNT(*) FROM contributions WHERE verified = 1"
        ).fetchone()
        verified = verified_row[0] if verified_row else 0

        nodes_row = self._conn.execute(
            "SELECT COUNT(DISTINCT relay_node_id) FROM contributions"
        ).fetchone()
        nodes = nodes_row[0] if nodes_row else 0

        top = self.top_contributors(limit=5)
        now = datetime.now(timezone.utc).isoformat()

        lines = [
            "=" * 78,
            "  BLACKHORSE MESH — CONTRIBUTION LEDGER REPORT",
            "=" * 78,
            f"  Generated : {now}",
            f"  Total receipts : {total}",
            f"  Verified       : {verified}",
            f"  Known nodes    : {nodes}",
            "",
            "  TOP CONTRIBUTORS",
            "-" * 78,
        ]
        if top:
            for i, c in enumerate(top, 1):
                score = f"{c['trust_score']:.3f}"
                given = c["given"]
                kb = c["bytes_given"] // 1024
                nid = c["node_id"][:16]
                lines.append(
                    f"  {i:2d}. {nid}...  relays={given:5d}  kb={kb:8d}  trust={score}"
                )
        else:
            lines.append("  (no contributions recorded)")
        lines.append("=" * 78)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()
