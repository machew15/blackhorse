"""
Tests for blackhorse.mesh.flusher — QueueFlusher.

Covers:
- flush() returns FlushReport with correct counts on all-success scenario
- flush() correctly handles timeout (no receipt) → mark_failed
- flush() returns empty FlushReport when no nodes available
- FlushReport fields are correctly populated
- stop() terminates auto_flush thread without hanging
"""

import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from blackhorse.mesh.queue import MessageQueue, ACKNOWLEDGED, FAILED, PENDING
from blackhorse.mesh.detector import NodeDetector, NodeAdvertisement
from blackhorse.mesh.flusher import QueueFlusher, FlushReport


DUMMY_PUBKEY = b"\x02" * 32
DUMMY_PACKET = b"\xAB" * 64


def _make_session_mock(receipt_bytes=None):
    """Create a mock BlackhorseSession with a verify_receipt that returns a ReceiptPayload."""
    mock = MagicMock()
    if receipt_bytes is not None:
        payload = MagicMock()
        payload.message_id = None  # will be set per-test
        mock.verify_receipt.return_value = payload
    else:
        mock.verify_receipt.side_effect = Exception("timeout simulated")
    return mock


def _make_detector_with_node(node_id="n1", address="127.0.0.1", signal=-50):
    detector = NodeDetector(scan_interval_seconds=30)
    node = NodeAdvertisement(
        node_id=node_id,
        address=address,
        last_seen=datetime.now(timezone.utc),
        signal_strength=signal,
    )
    detector.register_node(node)
    return detector


# ---------------------------------------------------------------------------
# FlushReport
# ---------------------------------------------------------------------------

def test_flush_report_fields():
    report = FlushReport(attempted=5, acknowledged=3, failed=2, timestamp=datetime.now(timezone.utc))
    assert report.attempted == 5
    assert report.acknowledged == 3
    assert report.failed == 2
    assert isinstance(report.timestamp, datetime)


# ---------------------------------------------------------------------------
# flush() — no nodes available
# ---------------------------------------------------------------------------

def test_flush_returns_empty_when_no_nodes(tmp_path):
    queue = MessageQueue(str(tmp_path / "q.db"))
    queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)

    detector = NodeDetector(scan_interval_seconds=30)  # no nodes registered
    session = MagicMock()
    signing_key = b"\x00" * 32

    flusher = QueueFlusher(queue, detector, session, signing_key)
    report = flusher.flush()

    assert report.attempted == 0
    assert report.acknowledged == 0
    assert report.failed == 0
    queue.close()


# ---------------------------------------------------------------------------
# flush() — send raises → mark_failed
# ---------------------------------------------------------------------------

def test_flush_marks_failed_on_send_error(tmp_path):
    queue = MessageQueue(str(tmp_path / "q.db"))
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)

    detector = _make_detector_with_node()
    session = MagicMock()
    signing_key = b"\x00" * 32

    flusher = QueueFlusher(queue, detector, session, signing_key, receipt_timeout_seconds=0.05)

    with patch.object(flusher, "_send_packet", side_effect=OSError("send failed")):
        report = flusher.flush()

    assert report.attempted == 1
    assert report.failed == 1
    assert report.acknowledged == 0
    queue.close()


# ---------------------------------------------------------------------------
# flush() — send succeeds but receipt times out → mark_failed
# ---------------------------------------------------------------------------

def test_flush_marks_failed_on_receipt_timeout(tmp_path):
    queue = MessageQueue(str(tmp_path / "q.db"))
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)

    detector = _make_detector_with_node()
    session = MagicMock()
    signing_key = b"\x00" * 32

    flusher = QueueFlusher(queue, detector, session, signing_key, receipt_timeout_seconds=0.05)

    with patch.object(flusher, "_send_packet"):
        with patch.object(flusher, "_await_receipt", return_value=None):
            report = flusher.flush()

    assert report.attempted == 1
    assert report.acknowledged == 0
    assert report.failed == 1
    queue.close()


# ---------------------------------------------------------------------------
# flush() — full success
# ---------------------------------------------------------------------------

def test_flush_marks_acknowledged_on_receipt(tmp_path):
    queue = MessageQueue(str(tmp_path / "q.db"))
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)

    detector = _make_detector_with_node()
    session = MagicMock()
    receipt_payload = MagicMock()
    receipt_payload.message_id = mid
    session.verify_receipt.return_value = receipt_payload
    signing_key = b"\x00" * 32

    flusher = QueueFlusher(queue, detector, session, signing_key, receipt_timeout_seconds=0.05)

    with patch.object(flusher, "_send_packet"):
        with patch.object(flusher, "_await_receipt", return_value=b"signed-receipt"):
            report = flusher.flush()

    assert report.attempted == 1
    assert report.acknowledged == 1
    assert report.failed == 0

    q_report = queue.status_report()
    assert q_report[ACKNOWLEDGED] == 1
    queue.close()


# ---------------------------------------------------------------------------
# flush() — mixed: one success, one timeout
# ---------------------------------------------------------------------------

def test_flush_mixed_results(tmp_path):
    queue = MessageQueue(str(tmp_path / "q.db"))
    mid1 = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY, priority=2)
    mid2 = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY, priority=1)

    detector = _make_detector_with_node()
    session = MagicMock()
    signing_key = b"\x00" * 32
    flusher = QueueFlusher(queue, detector, session, signing_key, receipt_timeout_seconds=0.05)

    call_count = [0]

    def fake_await(message_id, node):
        call_count[0] += 1
        # First call succeeds, second fails
        return b"receipt" if call_count[0] == 1 else None

    with patch.object(flusher, "_send_packet"):
        with patch.object(flusher, "_await_receipt", side_effect=fake_await):
            report = flusher.flush()

    assert report.attempted == 2
    assert report.acknowledged == 1
    assert report.failed == 1
    queue.close()


# ---------------------------------------------------------------------------
# stop() — does not hang
# ---------------------------------------------------------------------------

def test_stop_terminates_auto_flush(tmp_path):
    queue = MessageQueue(str(tmp_path / "q.db"))
    detector = _make_detector_with_node()
    session = MagicMock()
    signing_key = b"\x00" * 32

    flusher = QueueFlusher(queue, detector, session, signing_key)
    flusher.start_auto_flush()
    assert flusher._auto_thread is not None
    assert flusher._auto_thread.is_alive()

    flusher.stop()
    flusher._auto_thread.join(timeout=2.0)
    assert not flusher._auto_thread.is_alive()
    queue.close()
