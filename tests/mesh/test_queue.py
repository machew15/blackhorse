"""
Tests for blackhorse.mesh.queue — MessageQueue.

Covers:
- enqueue returns unique UUIDs
- peek ordering: priority DESC, timestamp ASC
- mark_sent increments retry_count
- mark_acknowledged sets ACKNOWLEDGED status
- mark_failed retry logic (reset to PENDING if count < 5, else FAILED)
- purge_acknowledged deletes only ACKNOWLEDGED rows and returns count
- status_report returns correct counts
"""

import time
import pytest

from blackhorse.mesh.queue import (
    MessageQueue,
    QueuedMessage,
    PENDING,
    SENT,
    ACKNOWLEDGED,
    FAILED,
    MAX_RETRY_COUNT,
)


@pytest.fixture
def queue(tmp_path):
    """Fresh in-memory queue backed by a temp file."""
    q = MessageQueue(str(tmp_path / "test.db"))
    yield q
    q.close()


DUMMY_PUBKEY = b"\x01" * 32
DUMMY_PACKET = b"\xAB\xCD" * 16


# ---------------------------------------------------------------------------
# enqueue
# ---------------------------------------------------------------------------

def test_enqueue_returns_string_id(queue):
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    assert isinstance(mid, str)
    assert len(mid) == 36  # UUID format


def test_enqueue_each_call_unique(queue):
    ids = {queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY) for _ in range(10)}
    assert len(ids) == 10


def test_enqueue_invalid_priority_raises(queue):
    with pytest.raises(ValueError):
        queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY, priority=4)
    with pytest.raises(ValueError):
        queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY, priority=0)


def test_enqueue_stores_packet_bytes(queue):
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    msgs = queue.peek(limit=1)
    assert msgs[0].packet_bytes == DUMMY_PACKET
    assert msgs[0].recipient_pubkey == DUMMY_PUBKEY


# ---------------------------------------------------------------------------
# peek — ordering
# ---------------------------------------------------------------------------

def test_peek_priority_desc_ordering(queue):
    queue.enqueue(b"normal", DUMMY_PUBKEY, priority=1)
    queue.enqueue(b"critical", DUMMY_PUBKEY, priority=3)
    queue.enqueue(b"high", DUMMY_PUBKEY, priority=2)

    msgs = queue.peek(limit=3)
    assert msgs[0].packet_bytes == b"critical"
    assert msgs[1].packet_bytes == b"high"
    assert msgs[2].packet_bytes == b"normal"


def test_peek_same_priority_timestamp_asc(queue):
    id1 = queue.enqueue(b"first", DUMMY_PUBKEY, priority=1)
    time.sleep(0.01)
    id2 = queue.enqueue(b"second", DUMMY_PUBKEY, priority=1)

    msgs = queue.peek(limit=2)
    assert msgs[0].message_id == id1
    assert msgs[1].message_id == id2


def test_peek_limit_respected(queue):
    for _ in range(5):
        queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    assert len(queue.peek(limit=3)) == 3


def test_peek_only_returns_pending(queue):
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    queue.mark_sent(mid)
    msgs = queue.peek(limit=10)
    assert all(m.message_id != mid for m in msgs)


# ---------------------------------------------------------------------------
# mark_sent
# ---------------------------------------------------------------------------

def test_mark_sent_sets_status(queue):
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    queue.mark_sent(mid)
    report = queue.status_report()
    assert report[SENT] == 1
    assert report[PENDING] == 0


def test_mark_sent_increments_retry_count(queue):
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    queue.mark_sent(mid)
    queue.mark_failed(mid)   # reset to PENDING (retry_count=1)
    queue.mark_sent(mid)     # retry_count → 2
    queue.mark_failed(mid)   # reset to PENDING (retry_count=2)

    msgs = queue.peek(limit=1)
    assert msgs[0].retry_count == 2


# ---------------------------------------------------------------------------
# mark_acknowledged
# ---------------------------------------------------------------------------

def test_mark_acknowledged_sets_status(queue):
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    queue.mark_sent(mid)
    queue.mark_acknowledged(mid)
    report = queue.status_report()
    assert report[ACKNOWLEDGED] == 1


# ---------------------------------------------------------------------------
# mark_failed — retry logic
# ---------------------------------------------------------------------------

def test_mark_failed_resets_to_pending_while_under_limit(queue):
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    queue.mark_sent(mid)
    queue.mark_failed(mid)  # retry_count=1, status → PENDING
    report = queue.status_report()
    assert report[PENDING] == 1


def test_mark_failed_sets_failed_at_limit(queue):
    mid = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    for _ in range(MAX_RETRY_COUNT):
        queue.mark_sent(mid)
        msgs = queue.peek(limit=1)
        # After mark_sent the message is SENT; simulate failure
        queue.mark_failed(mid)
        # If still pending, loop again
        pending = queue.peek(limit=1)
        if not pending:
            break  # now FAILED

    report = queue.status_report()
    assert report[FAILED] == 1


def test_mark_failed_nonexistent_id_is_noop(queue):
    queue.mark_failed("nonexistent-id")  # must not raise


# ---------------------------------------------------------------------------
# purge_acknowledged
# ---------------------------------------------------------------------------

def test_purge_acknowledged_deletes_correct_rows(queue):
    ids = [queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY) for _ in range(3)]
    queue.mark_sent(ids[0])
    queue.mark_acknowledged(ids[0])
    queue.mark_sent(ids[1])
    queue.mark_acknowledged(ids[1])

    deleted = queue.purge_acknowledged()
    assert deleted == 2
    report = queue.status_report()
    assert report[ACKNOWLEDGED] == 0
    assert report[PENDING] == 1


def test_purge_acknowledged_returns_zero_if_none(queue):
    queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    assert queue.purge_acknowledged() == 0


# ---------------------------------------------------------------------------
# status_report
# ---------------------------------------------------------------------------

def test_status_report_all_statuses(queue):
    mid1 = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    mid2 = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)
    mid3 = queue.enqueue(DUMMY_PACKET, DUMMY_PUBKEY)

    queue.mark_sent(mid1)
    queue.mark_acknowledged(mid1)

    queue.mark_sent(mid2)

    report = queue.status_report()
    assert report[PENDING] == 1
    assert report[SENT] == 1
    assert report[ACKNOWLEDGED] == 1
    assert report[FAILED] == 0
