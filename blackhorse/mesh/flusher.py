"""
Phase 1C — Queue Flush Controller.

When a relay node becomes available, QueueFlusher drains the pending message
queue in priority order (critical first, oldest first). Each delivery attempt:

1. Sends the packet via BlackhorseSession to the node with the highest
   signal_strength among the currently available nodes.
2. Awaits a signed delivery receipt (timeout: 10 seconds).
3. Updates the queue status accordingly.

QueueFlusher can run in auto-flush mode: it watches detector.is_connected()
and triggers flush() automatically whenever connectivity transitions from
False → True.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .queue import MessageQueue, QueuedMessage
from .detector import NodeDetector, NodeAdvertisement


# ---------------------------------------------------------------------------
# FlushReport dataclass
# ---------------------------------------------------------------------------

@dataclass
class FlushReport:
    """
    Summary of a single flush() operation.

    Attributes
    ----------
    attempted    : Number of messages for which delivery was attempted.
    acknowledged : Number of messages confirmed delivered (receipt received).
    failed       : Number of messages that timed out or errored.
    timestamp    : UTC datetime the flush cycle completed.
    """

    attempted: int
    acknowledged: int
    failed: int
    timestamp: datetime


# ---------------------------------------------------------------------------
# QueueFlusher
# ---------------------------------------------------------------------------

class QueueFlusher:
    """
    Drains the message queue whenever relay nodes are reachable.

    Parameters
    ----------
    queue       : The MessageQueue to flush.
    detector    : NodeDetector providing live node information.
    session     : A BlackhorseSession used to send packets and verify receipts.
    signing_key : 32-byte HMAC key used to verify delivery receipts.
    receipt_timeout_seconds : Seconds to wait for a delivery receipt (default 10).
    """

    def __init__(
        self,
        queue: MessageQueue,
        detector: NodeDetector,
        session: "BlackhorseSession",  # type: ignore[name-defined]
        signing_key: bytes,
        receipt_timeout_seconds: float = 10.0,
    ) -> None:
        self._queue = queue
        self._detector = detector
        self._session = session
        self._signing_key = signing_key
        self._receipt_timeout = receipt_timeout_seconds
        self._auto_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._was_connected: bool = False

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------

    def flush(self) -> FlushReport:
        """
        Flush up to 10 pending messages to the best available relay node.

        For each pending message:
        - Sends via BlackhorseSession to the node with the highest signal_strength.
        - Marks SENT immediately after transmission.
        - Waits up to receipt_timeout_seconds for a signed delivery receipt.
        - On receipt: marks ACKNOWLEDGED.
        - On timeout: marks FAILED (which resets to PENDING if retries remain).

        Returns
        -------
        FlushReport
            Summary counts for this flush cycle.
        """
        pending = self._queue.peek(limit=10)
        attempted = 0
        acknowledged = 0
        failed = 0

        best_node = self._best_node()
        if best_node is None:
            return FlushReport(
                attempted=0,
                acknowledged=0,
                failed=0,
                timestamp=datetime.now(timezone.utc),
            )

        for msg in pending:
            attempted += 1
            try:
                self._send_packet(msg, best_node)
                self._queue.mark_sent(msg.message_id)
            except Exception:
                self._queue.mark_failed(msg.message_id)
                failed += 1
                continue

            receipt = self._await_receipt(msg.message_id, best_node)
            if receipt is not None:
                self._queue.mark_acknowledged(msg.message_id)
                acknowledged += 1
            else:
                self._queue.mark_failed(msg.message_id)
                failed += 1

        return FlushReport(
            attempted=attempted,
            acknowledged=acknowledged,
            failed=failed,
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Auto-flush
    # ------------------------------------------------------------------

    def start_auto_flush(self) -> None:
        """
        Watch detector.is_connected() and trigger flush() on connect events.

        Runs in a background daemon thread. When connectivity transitions
        from False to True, a full flush() is executed.
        """
        if self._auto_thread and self._auto_thread.is_alive():
            return
        self._stop_event.clear()
        self._auto_thread = threading.Thread(
            target=self._auto_flush_loop,
            daemon=True,
            name="bhp-queue-flusher",
        )
        self._auto_thread.start()

    def _auto_flush_loop(self) -> None:
        """Background thread: poll connectivity and flush on transition."""
        while not self._stop_event.is_set():
            now_connected = self._detector.is_connected()
            if now_connected and not self._was_connected:
                try:
                    self.flush()
                except Exception:
                    pass
            self._was_connected = now_connected
            self._stop_event.wait(timeout=5.0)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Stop the auto-flush background thread cleanly."""
        self._stop_event.set()
        if self._auto_thread:
            self._auto_thread.join(timeout=10.0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _best_node(self) -> Optional[NodeAdvertisement]:
        """Return the live node with the highest signal_strength, or None."""
        nodes = self._detector.get_available_nodes()
        if not nodes:
            return None
        return max(nodes, key=lambda n: n.signal_strength)

    def _send_packet(self, msg: QueuedMessage, node: NodeAdvertisement) -> None:
        """
        Transmit a queued packet to the given relay node.

        The packet_bytes are already encrypted; this method wraps them in
        a UDP datagram addressed to the node. In a real deployment this
        would use BlackhorseSession.pack() for any additional framing.

        Parameters
        ----------
        msg  : The QueuedMessage whose packet_bytes to send.
        node : The destination NodeAdvertisement.
        """
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(msg.packet_bytes, (node.address, 51820))

    def _await_receipt(
        self,
        message_id: str,
        node: NodeAdvertisement,
    ) -> Optional[bytes]:
        """
        Wait for a signed delivery receipt for the given message_id.

        Listens on a UDP socket for the receipt_timeout duration.
        Validates the receipt using BlackhorseSession.verify_receipt().

        Parameters
        ----------
        message_id : The message_id to match in the receipt.
        node       : The node from which the receipt is expected.

        Returns
        -------
        bytes | None
            The raw receipt bytes on success, or None on timeout / invalid receipt.
        """
        import socket
        deadline = time.monotonic() + self._receipt_timeout
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(max(0.1, deadline - time.monotonic()))
                try:
                    sock.bind(("", 51821))
                except OSError:
                    pass
                while time.monotonic() < deadline:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    sock.settimeout(remaining)
                    try:
                        data, addr = sock.recvfrom(4096)
                    except (socket.timeout, OSError):
                        break
                    try:
                        payload = self._session.verify_receipt(data, self._signing_key)
                        if payload.message_id == message_id:
                            return data
                    except Exception:
                        continue
        except OSError:
            pass
        return None

    def __repr__(self) -> str:
        report = self._queue.status_report()
        return (
            f"QueueFlusher("
            f"pending={report.get('PENDING', 0)}, "
            f"connected={self._detector.is_connected()})"
        )
