"""
Phase 1A — Local Message Queue Engine.

Persistent, priority-ordered, SQLite-backed offline message queue.
All bytes stored in the queue are post-encryption — no plaintext ever
reaches disk.

Queue ordering: priority DESC, timestamp ASC (critical first, oldest first).

Status lifecycle:
    PENDING → SENT → ACKNOWLEDGED
    SENT    → PENDING  (on failure, if retry_count < 5)
    SENT    → FAILED   (on failure, if retry_count >= 5)
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

PENDING = "PENDING"
SENT = "SENT"
ACKNOWLEDGED = "ACKNOWLEDGED"
FAILED = "FAILED"

MAX_RETRY_COUNT: int = 5

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS message_queue (
    message_id    TEXT PRIMARY KEY,
    timestamp     TEXT NOT NULL,
    priority      INTEGER NOT NULL DEFAULT 1,
    status        TEXT NOT NULL DEFAULT 'PENDING',
    retry_count   INTEGER NOT NULL DEFAULT 0,
    recipient_pubkey BLOB NOT NULL,
    packet_bytes  BLOB NOT NULL
);
"""

_INDEX_STATUS_PRIORITY = """
CREATE INDEX IF NOT EXISTS idx_status_priority
    ON message_queue (status, priority DESC, timestamp ASC);
"""


# ---------------------------------------------------------------------------
# QueuedMessage dataclass
# ---------------------------------------------------------------------------

@dataclass
class QueuedMessage:
    """
    A single entry in the offline message queue.

    Attributes
    ----------
    message_id       : UUID string uniquely identifying this message.
    timestamp        : UTC datetime the message was enqueued.
    priority         : 1=normal, 2=high, 3=critical.
    status           : PENDING | SENT | ACKNOWLEDGED | FAILED.
    retry_count      : Number of send attempts made so far.
    packet_bytes     : Raw post-encryption packet bytes.
    recipient_pubkey : 32-byte X25519 public key of the intended recipient.
    """

    message_id: str
    timestamp: datetime
    priority: int
    status: str
    retry_count: int
    packet_bytes: bytes
    recipient_pubkey: bytes


# ---------------------------------------------------------------------------
# MessageQueue
# ---------------------------------------------------------------------------

class MessageQueue:
    """
    SQLite-backed offline message queue for the Blackhorse Mesh.

    All packet_bytes stored are post-encryption. No plaintext is ever
    written to disk. The queue survives power cycles because SQLite
    provides durable storage.

    Parameters
    ----------
    storage_path : Filesystem path to the SQLite database file.
    """

    def __init__(self, storage_path: str) -> None:
        self._db_path = storage_path
        self._conn = sqlite3.connect(storage_path, check_same_thread=False)
        self._conn.isolation_level = None  # autocommit
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_CREATE_TABLE)
        self._conn.execute(_INDEX_STATUS_PRIORITY)

    # ------------------------------------------------------------------
    # Enqueue
    # ------------------------------------------------------------------

    def enqueue(
        self,
        packet_bytes: bytes,
        recipient_pubkey: bytes,
        priority: int = 1,
    ) -> str:
        """
        Add a pre-signed, pre-encrypted BHL packet to the queue.

        Parameters
        ----------
        packet_bytes     : Raw post-encryption packet bytes (no plaintext).
        recipient_pubkey : 32-byte X25519 public key of the recipient.
        priority         : 1=normal, 2=high, 3=critical.

        Returns
        -------
        str
            UUID message_id for tracking.
        """
        if priority not in (1, 2, 3):
            raise ValueError(f"priority must be 1, 2, or 3; got {priority}")
        message_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO message_queue
                (message_id, timestamp, priority, status, retry_count,
                 recipient_pubkey, packet_bytes)
            VALUES (?, ?, ?, ?, 0, ?, ?)
            """,
            (message_id, ts, priority, PENDING, recipient_pubkey, packet_bytes),
        )
        return message_id

    # ------------------------------------------------------------------
    # Peek
    # ------------------------------------------------------------------

    def peek(self, limit: int = 10) -> list[QueuedMessage]:
        """
        Return the next *limit* pending messages, priority DESC then timestamp ASC.

        Parameters
        ----------
        limit : Maximum number of messages to return.

        Returns
        -------
        list[QueuedMessage]
            Ordered slice of the pending queue.
        """
        rows = self._conn.execute(
            """
            SELECT message_id, timestamp, priority, status, retry_count,
                   packet_bytes, recipient_pubkey
            FROM   message_queue
            WHERE  status = ?
            ORDER  BY priority DESC, timestamp ASC
            LIMIT  ?
            """,
            (PENDING, limit),
        ).fetchall()
        return [self._row_to_msg(r) for r in rows]

    # ------------------------------------------------------------------
    # Status transitions
    # ------------------------------------------------------------------

    def mark_sent(self, message_id: str) -> None:
        """
        Transition a message to SENT and increment retry_count.

        Parameters
        ----------
        message_id : UUID of the message to update.
        """
        self._conn.execute(
            """
            UPDATE message_queue
            SET    status = ?, retry_count = retry_count + 1
            WHERE  message_id = ?
            """,
            (SENT, message_id),
        )

    def mark_acknowledged(self, message_id: str) -> None:
        """
        Transition a message to ACKNOWLEDGED (terminal success state).

        Parameters
        ----------
        message_id : UUID of the message to update.
        """
        self._conn.execute(
            "UPDATE message_queue SET status = ? WHERE message_id = ?",
            (ACKNOWLEDGED, message_id),
        )

    def mark_failed(self, message_id: str) -> None:
        """
        Handle delivery failure for a message.

        If retry_count >= MAX_RETRY_COUNT, marks as FAILED (terminal).
        Otherwise resets status to PENDING for a future delivery attempt.

        Parameters
        ----------
        message_id : UUID of the message to update.
        """
        row = self._conn.execute(
            "SELECT retry_count FROM message_queue WHERE message_id = ?",
            (message_id,),
        ).fetchone()
        if row is None:
            return
        retry_count = row[0]
        if retry_count >= MAX_RETRY_COUNT:
            self._conn.execute(
                "UPDATE message_queue SET status = ? WHERE message_id = ?",
                (FAILED, message_id),
            )
        else:
            self._conn.execute(
                "UPDATE message_queue SET status = ? WHERE message_id = ?",
                (PENDING, message_id),
            )

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def purge_acknowledged(self) -> int:
        """
        Delete all ACKNOWLEDGED messages from the queue.

        Returns
        -------
        int
            Number of messages deleted.
        """
        cur = self._conn.execute(
            "DELETE FROM message_queue WHERE status = ?", (ACKNOWLEDGED,)
        )
        return cur.rowcount

    def status_report(self) -> dict[str, int]:
        """
        Return a count of messages by status.

        Returns
        -------
        dict[str, int]
            Keys: PENDING, SENT, ACKNOWLEDGED, FAILED. Values: counts.
        """
        report: dict[str, int] = {PENDING: 0, SENT: 0, ACKNOWLEDGED: 0, FAILED: 0}
        rows = self._conn.execute(
            "SELECT status, COUNT(*) FROM message_queue GROUP BY status"
        ).fetchall()
        for status, count in rows:
            if status in report:
                report[status] = count
        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_msg(row: Sequence) -> QueuedMessage:
        """Convert a SQLite row tuple to a QueuedMessage dataclass."""
        message_id, ts_str, priority, status, retry_count, packet_bytes, recipient_pubkey = row
        ts = datetime.fromisoformat(ts_str)
        return QueuedMessage(
            message_id=message_id,
            timestamp=ts,
            priority=priority,
            status=status,
            retry_count=retry_count,
            packet_bytes=bytes(packet_bytes),
            recipient_pubkey=bytes(recipient_pubkey),
        )

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    def __repr__(self) -> str:
        report = self.status_report()
        return (
            f"MessageQueue(path={self._db_path!r}, "
            f"pending={report[PENDING]}, sent={report[SENT]}, "
            f"acked={report[ACKNOWLEDGED]}, failed={report[FAILED]})"
        )
