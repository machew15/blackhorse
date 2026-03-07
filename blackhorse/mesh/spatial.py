"""
Phase 2A — Spatial Data Layer.

SpatialRecord captures a node's geographic position and sensor readings.
SpatialPacker serialises records through the Blackhorse BHL pipeline
(BHL encode → compress → HMAC-SHA256 sign) for broadcast or storage.

Sequence numbers on each record provide replay attack prevention: any
packet with a sequence number less than or equal to the last seen value
from that node_id is rejected with a ReplayError.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..language.encoder import BHLEncoder
from ..language.decoder import BHLDecoder
from ..compression.engine import compress, decompress
from ..crypto.signing.hmac_bhl import BHLSigner, SigningError


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ReplayError(Exception):
    """Raised when a SpatialRecord's sequence number is not strictly increasing."""


# ---------------------------------------------------------------------------
# SpatialRecord
# ---------------------------------------------------------------------------

@dataclass
class SpatialRecord:
    """
    A node's geographic position, sensor snapshot, and replay-prevention counter.

    Attributes
    ----------
    node_id      : Hex SHA-256 of the node's public key.
    latitude     : WGS84 latitude in degrees. 0.0 if unknown.
    longitude    : WGS84 longitude in degrees. 0.0 if unknown.
    altitude_m   : Altitude in metres above sea level. 0.0 if unavailable.
    accuracy_m   : GPS accuracy estimate in metres. -1.0 if unknown.
    timestamp    : UTC datetime of the reading.
    sensor_data  : Arbitrary key-value sensor readings (e.g. temperature).
    sequence     : Monotonic integer counter per node. Replay prevention.
    """

    node_id: str
    latitude: float
    longitude: float
    altitude_m: float
    accuracy_m: float
    timestamp: datetime
    sensor_data: dict[str, Any]
    sequence: int

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict."""
        return {
            "node_id": self.node_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "accuracy_m": self.accuracy_m,
            "timestamp": self.timestamp.isoformat(),
            "sensor_data": self.sensor_data,
            "sequence": self.sequence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SpatialRecord":
        """Reconstruct from a JSON-safe dict."""
        return cls(
            node_id=data["node_id"],
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            altitude_m=float(data["altitude_m"]),
            accuracy_m=float(data["accuracy_m"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            sensor_data=data.get("sensor_data", {}),
            sequence=int(data["sequence"]),
        )

    def has_gps_fix(self) -> bool:
        """Return True if this record carries a real GPS position."""
        return self.accuracy_m >= 0.0 and (self.latitude != 0.0 or self.longitude != 0.0)


# ---------------------------------------------------------------------------
# SpatialPacker
# ---------------------------------------------------------------------------

class SpatialPacker:
    """
    Serialises and deserialises SpatialRecord objects through the Blackhorse
    BHL pipeline (BHL encode → compress → HMAC-SHA256 sign).

    Spatial records are broadcast data — they do not have a single recipient
    — so the pipeline uses the signing layer without asymmetric key exchange.
    Records can be placed directly in the MessageQueue for peer distribution.

    Parameters
    ----------
    node_id     : Hex SHA-256 of this node's public key (used as packet origin).
    signing_key : 32-byte HMAC key for signing outbound records.
    session     : BlackhorseSession reference (provides BHLEncoder/Decoder paths
                  and allows future extension with encrypt_to_peer()).
    """

    def __init__(
        self,
        node_id: str,
        signing_key: bytes,
        session: Any,
    ) -> None:
        self._node_id = node_id
        self._signing_key = signing_key
        self._session = session
        self._last_seen_sequences: dict[str, int] = {}

    def pack(self, record: SpatialRecord) -> bytes:
        """
        Serialise a SpatialRecord through the BHL pipeline.

        Pipeline: JSON → UTF-8 → BHL encode → LZ77 compress → HMAC-SHA256 sign.

        Parameters
        ----------
        record : The SpatialRecord to pack.

        Returns
        -------
        bytes
            Signed, compressed, BHL-encoded packet bytes.
        """
        json_bytes = json.dumps(
            record.to_dict(), separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        bhl_bytes = BHLEncoder().encode_bytes(json_bytes)
        compressed = compress(bhl_bytes)
        return BHLSigner().sign(compressed, self._signing_key)

    def unpack(self, packet_bytes: bytes, signing_key: bytes) -> SpatialRecord:
        """
        Verify and deserialise a packed SpatialRecord.

        Raises ReplayError if the record's sequence number is not strictly
        greater than the last seen sequence from that node_id.

        Parameters
        ----------
        packet_bytes : Bytes produced by pack().
        signing_key  : HMAC key used to verify the packet signature.

        Returns
        -------
        SpatialRecord

        Raises
        ------
        ReplayError
            If sequence <= last seen for this node_id.
        SigningError
            If HMAC verification fails.
        """
        compressed = BHLSigner().verify_and_extract(packet_bytes, signing_key)
        bhl_bytes = decompress(compressed)
        json_bytes = BHLDecoder().decode_bytes(bhl_bytes)
        record = SpatialRecord.from_dict(json.loads(json_bytes.decode("utf-8")))

        last_seq = self._last_seen_sequences.get(record.node_id, -1)
        if record.sequence <= last_seq:
            raise ReplayError(
                f"Replay detected for node {record.node_id}: "
                f"received sequence {record.sequence} <= last seen {last_seq}"
            )
        self._last_seen_sequences[record.node_id] = record.sequence
        return record

    @staticmethod
    def generate_node_id(public_key_bytes: bytes) -> str:
        """
        Derive a node_id from raw public key bytes.

        Parameters
        ----------
        public_key_bytes : Raw public key bytes (any length).

        Returns
        -------
        str
            Hex-encoded SHA-256 digest of the public key.
        """
        return hashlib.sha256(public_key_bytes).hexdigest()
