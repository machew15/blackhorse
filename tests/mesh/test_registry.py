"""
Tests for blackhorse.mesh.registry — SpatialRegistry, Haversine, GeoJSON.

Covers:
- upsert() stores and retrieves records
- upsert() rejects lower-or-equal sequence numbers (replay protection)
- get_node() returns None for unknown node_id
- get_nearby() Haversine filtering (correct and incorrect radius)
- get_nearby() excludes nodes without GPS fix
- get_all() returns all nodes ordered by last_seen DESC
- node_count() returns correct count
- export_geojson() produces valid FeatureCollection structure
- export_geojson() includes null geometry for no-GPS-fix nodes
"""

import json
import pytest
from datetime import datetime, timezone

from blackhorse.mesh.spatial import SpatialRecord
from blackhorse.mesh.registry import SpatialRegistry, _haversine_km


PACKET = b"\xAA" * 32


def _rec(node_id: str, seq: int, lat: float = 51.5, lon: float = -0.1,
         acc: float = 5.0) -> SpatialRecord:
    return SpatialRecord(
        node_id=node_id,
        latitude=lat,
        longitude=lon,
        altitude_m=0.0,
        accuracy_m=acc,
        timestamp=datetime.now(timezone.utc),
        sensor_data={},
        sequence=seq,
    )


@pytest.fixture
def reg(tmp_path):
    r = SpatialRegistry(str(tmp_path / "reg.db"))
    yield r
    r.close()


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def test_haversine_same_point():
    assert _haversine_km(51.5, -0.1, 51.5, -0.1) == pytest.approx(0.0, abs=1e-6)


def test_haversine_london_paris_approx():
    # London to Paris is roughly 340 km
    dist = _haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
    assert 330.0 < dist < 360.0


def test_haversine_symmetric():
    d1 = _haversine_km(40.0, -74.0, 51.5, -0.1)
    d2 = _haversine_km(51.5, -0.1, 40.0, -74.0)
    assert d1 == pytest.approx(d2, rel=1e-6)


# ---------------------------------------------------------------------------
# upsert / get_node
# ---------------------------------------------------------------------------

def test_upsert_and_get_node(reg):
    record = _rec("n1", seq=0)
    reg.upsert(record, PACKET)
    result = reg.get_node("n1")
    assert result is not None
    assert result.node_id == "n1"
    assert result.sequence == 0


def test_get_node_returns_none_for_unknown(reg):
    assert reg.get_node("nonexistent") is None


def test_upsert_updates_on_higher_sequence(reg):
    reg.upsert(_rec("n1", seq=0, lat=10.0, lon=10.0), PACKET)
    reg.upsert(_rec("n1", seq=1, lat=20.0, lon=20.0), PACKET)
    result = reg.get_node("n1")
    assert result.latitude == pytest.approx(20.0)
    assert result.sequence == 1


def test_upsert_rejects_equal_sequence(reg):
    reg.upsert(_rec("n1", seq=5), PACKET)
    reg.upsert(_rec("n1", seq=5, lat=99.0, lon=99.0), PACKET)
    result = reg.get_node("n1")
    assert result.latitude != pytest.approx(99.0)


def test_upsert_rejects_lower_sequence(reg):
    reg.upsert(_rec("n1", seq=10), PACKET)
    reg.upsert(_rec("n1", seq=3, lat=99.0, lon=99.0), PACKET)
    result = reg.get_node("n1")
    assert result.sequence == 10


def test_upsert_stores_packet_hash(reg):
    reg.upsert(_rec("n1", seq=0), PACKET)
    row = reg._conn.execute(
        "SELECT packet_hash FROM node_registry WHERE node_id = ?", ("n1",)
    ).fetchone()
    assert row is not None
    assert len(row[0]) == 64  # SHA-256 hex


# ---------------------------------------------------------------------------
# get_nearby
# ---------------------------------------------------------------------------

def test_get_nearby_returns_close_node(reg):
    reg.upsert(_rec("close", seq=0, lat=51.5, lon=-0.1), PACKET)
    reg.upsert(_rec("far",   seq=0, lat=48.8, lon=2.35), PACKET)
    results = reg.get_nearby(51.5, -0.1, radius_km=10.0)
    ids = [r.node_id for r in results]
    assert "close" in ids
    assert "far" not in ids


def test_get_nearby_excludes_no_gps(reg):
    reg.upsert(_rec("no_gps", seq=0, lat=0.0, lon=0.0, acc=-1.0), PACKET)
    results = reg.get_nearby(51.5, -0.1, radius_km=10000.0)
    assert all(r.node_id != "no_gps" for r in results)


def test_get_nearby_ordered_nearest_first(reg):
    reg.upsert(_rec("n1", seq=0, lat=51.50, lon=-0.10), PACKET)
    reg.upsert(_rec("n2", seq=0, lat=51.52, lon=-0.12), PACKET)
    reg.upsert(_rec("n3", seq=0, lat=51.55, lon=-0.15), PACKET)
    results = reg.get_nearby(51.50, -0.10, radius_km=100.0)
    ids = [r.node_id for r in results]
    assert ids[0] == "n1"


# ---------------------------------------------------------------------------
# node_count / get_all
# ---------------------------------------------------------------------------

def test_node_count(reg):
    assert reg.node_count() == 0
    reg.upsert(_rec("a", seq=0), PACKET)
    reg.upsert(_rec("b", seq=0), PACKET)
    assert reg.node_count() == 2


def test_get_all_returns_all(reg):
    for i, nid in enumerate(["x", "y", "z"]):
        reg.upsert(_rec(nid, seq=i), PACKET)
    assert len(reg.get_all()) == 3


# ---------------------------------------------------------------------------
# GeoJSON export
# ---------------------------------------------------------------------------

def test_export_geojson_structure(reg):
    reg.upsert(_rec("n1", seq=0), PACKET)
    geojson_str = reg.export_geojson()
    data = json.loads(geojson_str)
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)


def test_export_geojson_feature_structure(reg):
    reg.upsert(_rec("n1", seq=0, lat=51.5, lon=-0.1), PACKET)
    data = json.loads(reg.export_geojson())
    feature = data["features"][0]
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    assert "node_id" in feature["properties"]


def test_export_geojson_null_geometry_for_no_gps(reg):
    reg.upsert(_rec("nogps", seq=0, lat=0.0, lon=0.0, acc=-1.0), PACKET)
    data = json.loads(reg.export_geojson())
    feature = next(f for f in data["features"] if f["properties"]["node_id"] == "nogps")
    assert feature["geometry"] is None


def test_export_geojson_coordinates_order(reg):
    # GeoJSON spec: coordinates are [longitude, latitude, altitude]
    reg.upsert(_rec("n1", seq=0, lat=51.5, lon=-0.1), PACKET)
    data = json.loads(reg.export_geojson())
    coords = data["features"][0]["geometry"]["coordinates"]
    assert coords[0] == pytest.approx(-0.1)  # longitude first
    assert coords[1] == pytest.approx(51.5)  # latitude second
