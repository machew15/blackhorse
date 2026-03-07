"""
Phase 1B — Node Detection.

Scans the local network for devices broadcasting the Blackhorse handshake
beacon (BHP magic bytes b"BHP\\x1A" on UDP port 51820).

The NodeDetector maintains an in-memory registry of recently-seen nodes.
A node is considered "live" if it was seen within the last 2x scan_interval.

NodeAdvertisement fields include an optional expiry datetime (Phase 4D key
expiry). Nodes with expired keys are excluded from the live node list.
"""

from __future__ import annotations

import hashlib
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional


# BHP beacon magic — the first 4 bytes of any Blackhorse Protocol packet
BHP_BEACON_MAGIC: bytes = b"BHP\x1A"
UDP_BEACON_PORT: int = 51820
BEACON_RECV_TIMEOUT: float = 2.0  # seconds per receive poll
BEACON_BUFFER_SIZE: int = 4096


# ---------------------------------------------------------------------------
# NodeAdvertisement dataclass
# ---------------------------------------------------------------------------

@dataclass
class NodeAdvertisement:
    """
    A discovered Blackhorse mesh node.

    Attributes
    ----------
    node_id         : Hex string derived from the SHA-256 of the node's public key.
    address         : IP address (or MAC if IP unavailable) of the node.
    last_seen       : UTC datetime of the most recent beacon reception.
    signal_strength : RSSI in dBm if available, -1 if not measurable.
    public_key_hint : First 8 bytes of the node's public key (from beacon),
                      or empty bytes if the beacon carries no key material.
    expiry          : Optional UTC datetime after which this node's key is
                      considered expired. None means no expiry set.
    """

    node_id: str
    address: str
    last_seen: datetime
    signal_strength: int = -1
    public_key_hint: bytes = field(default_factory=bytes)
    expiry: Optional[datetime] = None

    def is_expired(self) -> bool:
        """Return True if this node's key has passed its expiry datetime."""
        if self.expiry is None:
            return False
        return datetime.now(timezone.utc) >= self.expiry


# ---------------------------------------------------------------------------
# NodeDetector
# ---------------------------------------------------------------------------

class NodeDetector:
    """
    Scans for Blackhorse mesh nodes broadcasting UDP beacons.

    Listens on UDP port 51820 for packets whose first 4 bytes match the
    BHP magic (``b"BHP\\x1A"``). Each matching sender is recorded as a
    NodeAdvertisement.

    Parameters
    ----------
    interface            : Network interface to bind to (default "wlan0").
    scan_interval_seconds: Seconds between active scan cycles (default 30).
    """

    def __init__(
        self,
        interface: str = "wlan0",
        scan_interval_seconds: int = 30,
    ) -> None:
        self._interface = interface
        self._interval = scan_interval_seconds
        self._nodes: dict[str, NodeAdvertisement] = {}
        self._lock = threading.Lock()
        self._bg_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Active scan
    # ------------------------------------------------------------------

    def scan(self) -> list[NodeAdvertisement]:
        """
        Perform a single scan for Blackhorse beacon packets.

        Opens a UDP socket bound to the beacon port and collects any
        packets whose payload begins with the BHP magic. Each valid
        sender is parsed into a NodeAdvertisement and recorded.

        Returns
        -------
        list[NodeAdvertisement]
            All nodes discovered during this scan cycle.
        """
        discovered: list[NodeAdvertisement] = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(BEACON_RECV_TIMEOUT)
                try:
                    sock.bind(("", UDP_BEACON_PORT))
                except OSError:
                    # Port already bound; use a raw listen approach
                    pass

                deadline = time.monotonic() + BEACON_RECV_TIMEOUT
                while time.monotonic() < deadline:
                    try:
                        data, addr = sock.recvfrom(BEACON_BUFFER_SIZE)
                    except (socket.timeout, OSError):
                        break
                    node = self._parse_beacon(data, addr[0])
                    if node is not None:
                        discovered.append(node)
                        with self._lock:
                            self._nodes[node.node_id] = node
        except OSError:
            pass  # Socket creation failed (no interface, no permission); handled gracefully
        return discovered

    # ------------------------------------------------------------------
    # Background scanning
    # ------------------------------------------------------------------

    def start_background_scan(self) -> None:
        """
        Start scanning in a daemon background thread.

        Calls ``scan()`` every ``scan_interval_seconds`` seconds.
        The thread runs until ``stop()`` is called.
        """
        if self._bg_thread and self._bg_thread.is_alive():
            return
        self._stop_event.clear()
        self._bg_thread = threading.Thread(
            target=self._scan_loop,
            daemon=True,
            name="bhp-node-detector",
        )
        self._bg_thread.start()

    def _scan_loop(self) -> None:
        """Background thread body: scan repeatedly until stop_event is set."""
        while not self._stop_event.is_set():
            self.scan()
            self._stop_event.wait(timeout=self._interval)

    # ------------------------------------------------------------------
    # Node registry queries
    # ------------------------------------------------------------------

    def get_available_nodes(self) -> list[NodeAdvertisement]:
        """
        Return all live, non-expired nodes seen within the last 2x scan_interval.

        A node is considered stale if more than ``2 * scan_interval_seconds``
        seconds have elapsed since its last beacon. Expired-key nodes are excluded.

        Returns
        -------
        list[NodeAdvertisement]
            Nodes currently considered reachable.
        """
        cutoff = timedelta(seconds=2 * self._interval)
        now = datetime.now(timezone.utc)
        with self._lock:
            return [
                node
                for node in self._nodes.values()
                if (now - node.last_seen) <= cutoff and not node.is_expired()
            ]

    def is_connected(self) -> bool:
        """
        Return True if at least one live node is currently available.

        Returns
        -------
        bool
        """
        return len(self.get_available_nodes()) > 0

    # ------------------------------------------------------------------
    # Manual node registration (for testing and internal use)
    # ------------------------------------------------------------------

    def register_node(self, node: NodeAdvertisement) -> None:
        """
        Manually register a NodeAdvertisement in the internal registry.

        Useful for injecting nodes during testing or from a trusted
        out-of-band source (e.g., a Bluetooth handshake).

        Parameters
        ----------
        node : The NodeAdvertisement to register.
        """
        with self._lock:
            self._nodes[node.node_id] = node

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Stop the background scan thread cleanly."""
        self._stop_event.set()
        if self._bg_thread:
            self._bg_thread.join(timeout=self._interval + 1)

    # ------------------------------------------------------------------
    # Beacon parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_beacon(data: bytes, address: str) -> NodeAdvertisement | None:
        """
        Parse a raw UDP packet into a NodeAdvertisement, or None if invalid.

        A valid beacon starts with BHP_BEACON_MAGIC. The node_id is derived
        from the SHA-256 of bytes 4–36 (the 32-byte public key in BHP packets)
        if present, or from the SHA-256 of the sender address otherwise.
        """
        if len(data) < 4 or data[:4] != BHP_BEACON_MAGIC:
            return None

        if len(data) >= 36:
            pubkey_hint = data[4:12]  # first 8 bytes of the public key field
            node_id = hashlib.sha256(data[4:36]).hexdigest()[:16]
        else:
            pubkey_hint = b""
            node_id = hashlib.sha256(address.encode()).hexdigest()[:16]

        return NodeAdvertisement(
            node_id=node_id,
            address=address,
            last_seen=datetime.now(timezone.utc),
            signal_strength=-1,
            public_key_hint=pubkey_hint,
        )

    def __repr__(self) -> str:
        with self._lock:
            n = len(self._nodes)
        live = len(self.get_available_nodes())
        return (
            f"NodeDetector(interface={self._interface!r}, "
            f"known={n}, live={live})"
        )
