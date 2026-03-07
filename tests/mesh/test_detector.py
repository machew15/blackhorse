"""
Tests for blackhorse.mesh.detector — NodeDetector.

Covers:
- NodeAdvertisement parsing from raw UDP bytes
- is_expired() respects the expiry field
- Invalid beacon bytes (wrong magic) are rejected
- Short beacon without public key still produces a node_id
- get_available_nodes() excludes stale nodes
- get_available_nodes() excludes expired-key nodes
- is_connected() True/False logic
- register_node() allows manual injection
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

import pytest

from blackhorse.mesh.detector import (
    NodeDetector,
    NodeAdvertisement,
    BHP_BEACON_MAGIC,
    UDP_BEACON_PORT,
)


# ---------------------------------------------------------------------------
# NodeAdvertisement
# ---------------------------------------------------------------------------

def test_node_advertisement_not_expired_when_no_expiry():
    node = NodeAdvertisement(
        node_id="abc123",
        address="10.0.0.1",
        last_seen=datetime.now(timezone.utc),
    )
    assert not node.is_expired()


def test_node_advertisement_not_expired_future():
    node = NodeAdvertisement(
        node_id="abc123",
        address="10.0.0.1",
        last_seen=datetime.now(timezone.utc),
        expiry=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert not node.is_expired()


def test_node_advertisement_expired_past():
    node = NodeAdvertisement(
        node_id="abc123",
        address="10.0.0.1",
        last_seen=datetime.now(timezone.utc),
        expiry=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    assert node.is_expired()


# ---------------------------------------------------------------------------
# Beacon parsing
# ---------------------------------------------------------------------------

def test_parse_valid_beacon_with_pubkey():
    pubkey = b"\x42" * 32
    beacon = BHP_BEACON_MAGIC + pubkey
    node = NodeDetector._parse_beacon(beacon, "192.168.1.5")
    assert node is not None
    assert node.address == "192.168.1.5"
    assert node.signal_strength == -1
    assert len(node.public_key_hint) == 8
    assert node.public_key_hint == pubkey[:8]


def test_parse_valid_beacon_short_no_pubkey():
    # Only 4 bytes: magic only, no pubkey
    beacon = BHP_BEACON_MAGIC
    node = NodeDetector._parse_beacon(beacon, "10.0.0.2")
    assert node is not None
    assert node.public_key_hint == b""
    assert node.address == "10.0.0.2"


def test_parse_invalid_magic_returns_none():
    bad = b"XXXX" + b"\x00" * 32
    node = NodeDetector._parse_beacon(bad, "10.0.0.3")
    assert node is None


def test_parse_empty_bytes_returns_none():
    node = NodeDetector._parse_beacon(b"", "10.0.0.4")
    assert node is None


def test_parse_beacon_node_id_is_deterministic():
    beacon = BHP_BEACON_MAGIC + b"\x99" * 32
    n1 = NodeDetector._parse_beacon(beacon, "1.2.3.4")
    n2 = NodeDetector._parse_beacon(beacon, "1.2.3.4")
    assert n1.node_id == n2.node_id


# ---------------------------------------------------------------------------
# get_available_nodes / is_connected
# ---------------------------------------------------------------------------

def _make_fresh_node(node_id: str, address: str) -> NodeAdvertisement:
    return NodeAdvertisement(
        node_id=node_id,
        address=address,
        last_seen=datetime.now(timezone.utc),
    )


def _make_stale_node(node_id: str, address: str, interval: int) -> NodeAdvertisement:
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=3 * interval)
    return NodeAdvertisement(
        node_id=node_id,
        address=address,
        last_seen=stale_time,
    )


def test_is_connected_false_when_no_nodes():
    detector = NodeDetector(scan_interval_seconds=30)
    assert not detector.is_connected()


def test_is_connected_true_after_register():
    detector = NodeDetector(scan_interval_seconds=30)
    node = _make_fresh_node("n1", "10.0.0.1")
    detector.register_node(node)
    assert detector.is_connected()


def test_get_available_nodes_excludes_stale():
    detector = NodeDetector(scan_interval_seconds=10)
    fresh = _make_fresh_node("fresh", "10.0.0.1")
    stale = _make_stale_node("stale", "10.0.0.2", interval=10)
    detector.register_node(fresh)
    detector.register_node(stale)

    available = detector.get_available_nodes()
    ids = [n.node_id for n in available]
    assert "fresh" in ids
    assert "stale" not in ids


def test_get_available_nodes_excludes_expired_key():
    detector = NodeDetector(scan_interval_seconds=30)
    expired_node = NodeAdvertisement(
        node_id="expired",
        address="10.0.0.5",
        last_seen=datetime.now(timezone.utc),
        expiry=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    valid_node = _make_fresh_node("valid", "10.0.0.6")
    detector.register_node(expired_node)
    detector.register_node(valid_node)

    available = detector.get_available_nodes()
    ids = [n.node_id for n in available]
    assert "expired" not in ids
    assert "valid" in ids


def test_is_connected_false_when_all_stale():
    detector = NodeDetector(scan_interval_seconds=10)
    stale = _make_stale_node("stale", "10.0.0.2", interval=10)
    detector.register_node(stale)
    assert not detector.is_connected()
