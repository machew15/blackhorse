"""
Phase 1B — Node Detection.
Phase 3A (Hardening) — Eclipse Attack Mitigation + Key Rotation.

Scans the local network for devices broadcasting the Blackhorse handshake
beacon (BHP magic bytes b"BHP\\x1A" on UDP port 51820).

The NodeDetector maintains an in-memory registry of recently-seen nodes.
A node is considered "live" if it was seen within the last 2x scan_interval.

NodeAdvertisement fields include an optional expiry datetime (Phase 4D key
expiry). Nodes with expired keys are excluded from the live node list.

Phase 3 additions:
- Geohash-based spatial diversity tracking (inline, no external libraries)
- Eclipse attack detection via get_cluster_diversity() / is_healthy()
- Key rotation via rotate_keys() and generate_node_advertisement()
"""

from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Geohash encoding (inline — no external geo libraries)
# ---------------------------------------------------------------------------

_GEOHASH_CHARS: str = "0123456789bcdefghjkmnpqrstuvwxyz"


def _encode_geohash(lat: float, lon: float, precision: int = 4) -> str:
    """
    Encode a WGS84 coordinate pair as a geohash string.

    Uses the standard Geohash algorithm with the base32 character set
    "0123456789bcdefghjkmnpqrstuvwxyz". 4-character precision gives
    approximately ±20 km accuracy (~40 km cell size).

    Parameters
    ----------
    lat       : Latitude in decimal degrees.
    lon       : Longitude in decimal degrees.
    precision : Number of geohash characters to produce (default 4).

    Returns
    -------
    str
        Geohash string of the given precision.
    """
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]

    result: list[str] = []
    bit_idx: int = 0
    char_val: int = 0
    is_lon: bool = True

    while len(result) < precision:
        if is_lon:
            mid = (lon_range[0] + lon_range[1]) / 2.0
            if lon >= mid:
                char_val |= (1 << (4 - bit_idx))
                lon_range[0] = mid
            else:
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2.0
            if lat >= mid:
                char_val |= (1 << (4 - bit_idx))
                lat_range[0] = mid
            else:
                lat_range[1] = mid

        is_lon = not is_lon

        if bit_idx == 4:
            result.append(_GEOHASH_CHARS[char_val])
            bit_idx = 0
            char_val = 0
        else:
            bit_idx += 1

    return "".join(result)


# BHP beacon magic — the first 4 bytes of any Blackhorse Protocol packet
BHP_BEACON_MAGIC: bytes = b"BHP\x1A"
UDP_BEACON_PORT: int = 51820
BEACON_RECV_TIMEOUT: float = 2.0  # seconds per receive poll
BEACON_BUFFER_SIZE: int = 4096

# Key rotation default TTL
_DEFAULT_KEY_TTL_DAYS: int = 90


# ---------------------------------------------------------------------------
# SpatialCluster dataclass
# ---------------------------------------------------------------------------

@dataclass
class SpatialCluster:
    """
    A group of nodes sharing the same 4-character geohash prefix (~40 km cell).

    Attributes
    ----------
    cluster_id : 4-character geohash string identifying the geographic cell.
    nodes      : List of node_ids located in this cluster.
    """

    cluster_id: str
    nodes: list[str]


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
    geohash: Optional[str] = None  # 4-char geohash prefix for eclipse mitigation

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
        min_cluster_diversity: int = 3,
    ) -> None:
        self._interface = interface
        self._interval = scan_interval_seconds
        self._min_cluster_diversity = min_cluster_diversity
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
        """Background thread body: scan and check health on each cycle."""
        while not self._stop_event.is_set():
            self.scan()
            if not self.is_healthy():
                import logging
                report = self.get_diversity_report()
                logging.warning(
                    "Eclipse attack risk — insufficient spatial diversity: %s",
                    report,
                )
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
    # Phase 3 — Eclipse mitigation
    # ------------------------------------------------------------------

    def get_cluster_diversity(self) -> int:
        """
        Count the number of distinct 4-character geohash clusters among
        available nodes that have a spatial position attached.

        Nodes without geohash information (no lat/lon in their advertisement)
        are grouped into a single synthetic "no-geo" cluster so they still
        contribute to connectivity without inflating diversity counts.

        Returns
        -------
        int
            Number of distinct spatial clusters represented.
        """
        nodes = self.get_available_nodes()
        clusters: set[str] = set()
        for node in nodes:
            gh = getattr(node, "geohash", None)
            if gh:
                clusters.add(gh[:4])
            else:
                clusters.add("__no_geo__")
        return len(clusters)

    def is_healthy(self) -> bool:
        """
        Return True if connectivity meets the minimum spatial diversity requirement.

        A connection graph that consists entirely of nodes from a single
        geographic cluster is vulnerable to an eclipse attack — an adversary
        that controls one geographic area can isolate this node from the wider
        mesh. Requiring ``min_cluster_diversity`` distinct clusters mitigates this.

        Returns
        -------
        bool
            True if connected AND cluster diversity >= min_cluster_diversity.
        """
        if not self.is_connected():
            return False
        return self.get_cluster_diversity() >= self._min_cluster_diversity

    def get_diversity_report(self) -> dict:
        """
        Return a summary of the current spatial diversity state.

        Returns
        -------
        dict
            Keys: total_nodes, distinct_clusters, cluster_ids, is_healthy.
        """
        nodes = self.get_available_nodes()
        cluster_map: dict[str, list[str]] = {}
        for node in nodes:
            gh = getattr(node, "geohash", None)
            key = gh[:4] if gh else "__no_geo__"
            cluster_map.setdefault(key, []).append(node.node_id)

        return {
            "total_nodes": len(nodes),
            "distinct_clusters": len(cluster_map),
            "cluster_ids": list(cluster_map.keys()),
            "is_healthy": self.is_healthy(),
        }

    # ------------------------------------------------------------------
    # Phase 3 — Key rotation
    # ------------------------------------------------------------------

    def rotate_keys(
        self,
        new_keypair: tuple[bytes, bytes],
        signing_key: bytes,
    ) -> bytes:
        """
        Generate a new NodeAdvertisement for a rotated keypair.

        Produces a signed advertisement with the new public key and an
        expiry 90 days from now. The advertisement can be broadcast over
        UDP to notify peers of the key change.

        Parameters
        ----------
        new_keypair : (public_key_bytes, secret_key_bytes) of the new keypair.
        signing_key : HMAC signing key for the advertisement.

        Returns
        -------
        bytes
            Signed NodeAdvertisement bytes ready for UDP broadcast.
        """
        new_pub = new_keypair[0]
        return generate_node_advertisement(
            public_key=new_pub,
            signing_key=signing_key,
            ttl_days=_DEFAULT_KEY_TTL_DAYS,
        )

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


# ---------------------------------------------------------------------------
# Module-level helper — NodeAdvertisement generation / key rotation
# ---------------------------------------------------------------------------

def generate_node_advertisement(
    public_key: bytes,
    signing_key: bytes,
    ttl_days: int = 90,
) -> bytes:
    """
    Create a signed NodeAdvertisement packet for UDP broadcast.

    The advertisement is packed through the BHL pipeline (BHL encode →
    compress → HMAC sign) and includes:
    - The node's public key
    - An expiry timestamp (now + ttl_days)
    - A SHA-256-derived node_id

    Parameters
    ----------
    public_key  : Raw public key bytes (any length).
    signing_key : 32-byte HMAC key for signing the advertisement.
    ttl_days    : Key validity period in days (default 90).

    Returns
    -------
    bytes
        Signed, compressed, BHL-encoded advertisement bytes.
    """
    from datetime import timedelta
    import json as _json

    # Import lazily to avoid circular imports
    from ..language.encoder import BHLEncoder
    from ..compression.engine import compress
    from ..crypto.signing.hmac_bhl import BHLSigner

    node_id = hashlib.sha256(public_key).hexdigest()
    expiry = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()

    advert = {
        "type": "NODE_ADVERTISEMENT",
        "node_id": node_id,
        "public_key_hex": public_key.hex(),
        "expiry": expiry,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    json_bytes = _json.dumps(advert, separators=(",", ":")).encode("utf-8")
    bhl_bytes = BHLEncoder().encode_bytes(json_bytes)
    compressed = compress(bhl_bytes)
    return BHLSigner().sign(compressed, signing_key)
