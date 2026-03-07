"""
Phase 2B — Spatial Registry.

SQLite-backed store of known peer node locations. Supports:
- Upsert with replay-safe sequence checking
- Haversine proximity search (no external geo libraries)
- GeoJSON FeatureCollection export (RFC 7946)
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from typing import Sequence

from .spatial import SpatialRecord


# ---------------------------------------------------------------------------
# Haversine (inline, no external libraries)
# ---------------------------------------------------------------------------

_EARTH_RADIUS_KM: float = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance in kilometres between two WGS84 points.

    Parameters
    ----------
    lat1, lon1 : Latitude and longitude of point A in decimal degrees.
    lat2, lon2 : Latitude and longitude of point B in decimal degrees.

    Returns
    -------
    float
        Distance in kilometres.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_KM * c


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS node_registry (
    node_id       TEXT PRIMARY KEY,
    latitude      REAL NOT NULL DEFAULT 0.0,
    longitude     REAL NOT NULL DEFAULT 0.0,
    altitude_m    REAL NOT NULL DEFAULT 0.0,
    accuracy_m    REAL NOT NULL DEFAULT -1.0,
    last_seen     TEXT NOT NULL,
    last_sequence INTEGER NOT NULL DEFAULT -1,
    sensor_data   TEXT NOT NULL DEFAULT '{}',
    packet_hash   TEXT NOT NULL DEFAULT ''
);
"""


# ---------------------------------------------------------------------------
# SpatialRegistry
# ---------------------------------------------------------------------------

class SpatialRegistry:
    """
    SQLite store of known peer node locations.

    Supports proximity search via Haversine formula and GeoJSON export for
    external visualisation tools.

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

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert(self, record: SpatialRecord, packet_bytes: bytes) -> None:
        """
        Insert or update a node's location record.

        Rejects the update if record.sequence <= stored last_sequence,
        providing replay protection at the registry level.

        Parameters
        ----------
        record       : The SpatialRecord to store.
        packet_bytes : Raw packet bytes; SHA-256 is stored as packet_hash.
        """
        row = self._conn.execute(
            "SELECT last_sequence FROM node_registry WHERE node_id = ?",
            (record.node_id,),
        ).fetchone()
        if row is not None and record.sequence <= row[0]:
            return  # Reject replay

        packet_hash = hashlib.sha256(packet_bytes).hexdigest()
        self._conn.execute(
            """
            INSERT INTO node_registry
                (node_id, latitude, longitude, altitude_m, accuracy_m,
                 last_seen, last_sequence, sensor_data, packet_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(node_id) DO UPDATE SET
                latitude      = excluded.latitude,
                longitude     = excluded.longitude,
                altitude_m    = excluded.altitude_m,
                accuracy_m    = excluded.accuracy_m,
                last_seen     = excluded.last_seen,
                last_sequence = excluded.last_sequence,
                sensor_data   = excluded.sensor_data,
                packet_hash   = excluded.packet_hash
            """,
            (
                record.node_id,
                record.latitude,
                record.longitude,
                record.altitude_m,
                record.accuracy_m,
                record.timestamp.isoformat(),
                record.sequence,
                json.dumps(record.sensor_data, separators=(",", ":")),
                packet_hash,
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> SpatialRecord | None:
        """
        Retrieve a single node's most recent SpatialRecord.

        Parameters
        ----------
        node_id : The node_id to look up.

        Returns
        -------
        SpatialRecord | None
            None if the node is not in the registry.
        """
        row = self._conn.execute(
            "SELECT * FROM node_registry WHERE node_id = ?", (node_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def get_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[SpatialRecord]:
        """
        Return all nodes within radius_km kilometres of the given point.

        Uses Haversine formula. Only nodes with a valid GPS fix (accuracy_m >= 0)
        are considered; nodes with unknown positions (0.0, 0.0) are excluded.

        Parameters
        ----------
        latitude   : Query latitude in decimal degrees.
        longitude  : Query longitude in decimal degrees.
        radius_km  : Search radius in kilometres.

        Returns
        -------
        list[SpatialRecord]
            Nodes within the radius, ordered nearest-first.
        """
        rows = self._conn.execute("SELECT * FROM node_registry").fetchall()
        results = []
        for row in rows:
            record = self._row_to_record(row)
            if not record.has_gps_fix():
                continue
            dist = _haversine_km(latitude, longitude, record.latitude, record.longitude)
            if dist <= radius_km:
                results.append((dist, record))
        results.sort(key=lambda x: x[0])
        return [r for _, r in results]

    def get_all(self) -> list[SpatialRecord]:
        """
        Return all known nodes ordered by last_seen descending.

        Returns
        -------
        list[SpatialRecord]
        """
        rows = self._conn.execute(
            "SELECT * FROM node_registry ORDER BY last_seen DESC"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def node_count(self) -> int:
        """
        Return the total number of known nodes.

        Returns
        -------
        int
        """
        row = self._conn.execute(
            "SELECT COUNT(*) FROM node_registry"
        ).fetchone()
        return row[0] if row else 0

    # ------------------------------------------------------------------
    # GeoJSON export
    # ------------------------------------------------------------------

    def export_geojson(self) -> str:
        """
        Export all known nodes as a GeoJSON FeatureCollection (RFC 7946).

        Each node is a Point Feature. Nodes without a GPS fix are included
        with null geometry so the registry remains complete.

        Returns
        -------
        str
            Valid GeoJSON string.
        """
        features = []
        for record in self.get_all():
            geometry: dict | None
            if record.has_gps_fix():
                geometry = {
                    "type": "Point",
                    "coordinates": [record.longitude, record.latitude, record.altitude_m],
                }
            else:
                geometry = None

            feature = {
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "node_id": record.node_id,
                    "accuracy_m": record.accuracy_m,
                    "last_seen": record.timestamp.isoformat(),
                    "sequence": record.sequence,
                    **record.sensor_data,
                },
            }
            features.append(feature)

        return json.dumps(
            {
                "type": "FeatureCollection",
                "features": features,
            },
            separators=(",", ":"),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._conn.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: Sequence) -> SpatialRecord:
        (
            node_id, latitude, longitude, altitude_m, accuracy_m,
            last_seen, last_sequence, sensor_data_json, packet_hash,
        ) = row
        return SpatialRecord(
            node_id=node_id,
            latitude=float(latitude),
            longitude=float(longitude),
            altitude_m=float(altitude_m),
            accuracy_m=float(accuracy_m),
            timestamp=datetime.fromisoformat(last_seen),
            sensor_data=json.loads(sensor_data_json),
            sequence=int(last_sequence),
        )
