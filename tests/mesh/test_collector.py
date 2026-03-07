"""
Tests for blackhorse.mesh.collector — SpatialCollector, NMEA parsing.

Covers:
- NMEA sentence parsing functions (inline)
- _parse_gprmc valid / invalid / wrong-status
- _parse_gpgga valid / quality-zero / missing fields
- _parse_nmea_sentences integration
- SpatialCollector.read_gps() graceful when no hardware
- SpatialCollector.read_sensors() graceful when no sys files
- SpatialCollector.collect() returns SpatialRecord with zero coords if no GPS
- SpatialCollector.collect() auto-increments sequence
- stop() terminates background thread
"""

import time
import pytest

from blackhorse.mesh.collector import (
    _nmea_lat_to_decimal,
    _nmea_lon_to_decimal,
    _parse_gprmc,
    _parse_gpgga,
    _parse_nmea_sentences,
    SpatialCollector,
)
from blackhorse.mesh.spatial import SpatialPacker
from blackhorse.mesh.queue import MessageQueue
from blackhorse.interface.handshake import BlackhorseSession
from blackhorse.crypto.signing.hmac_bhl import BHLSigner


# ---------------------------------------------------------------------------
# NMEA coordinate conversion
# ---------------------------------------------------------------------------

def test_nmea_lat_north():
    assert _nmea_lat_to_decimal("5130.0000", "N") == pytest.approx(51.5)


def test_nmea_lat_south():
    assert _nmea_lat_to_decimal("3300.0000", "S") == pytest.approx(-33.0)


def test_nmea_lat_empty():
    assert _nmea_lat_to_decimal("", "N") == 0.0


def test_nmea_lon_west():
    assert _nmea_lon_to_decimal("00006.0000", "W") == pytest.approx(-0.1)


def test_nmea_lon_east():
    assert _nmea_lon_to_decimal("00006.0000", "E") == pytest.approx(0.1)


def test_nmea_lon_empty():
    assert _nmea_lon_to_decimal("", "E") == 0.0


# ---------------------------------------------------------------------------
# GPRMC parsing
# ---------------------------------------------------------------------------

def test_parse_gprmc_valid():
    sentence = "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
    result = _parse_gprmc(sentence)
    assert result is not None
    lat, lon = result
    assert lat == pytest.approx(48.0 + 7.038 / 60.0)
    assert lon == pytest.approx(11.0 + 31.0 / 60.0)


def test_parse_gprmc_invalid_status():
    sentence = "$GPRMC,123519,V,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"
    assert _parse_gprmc(sentence) is None


def test_parse_gprmc_too_short():
    assert _parse_gprmc("$GPRMC,123") is None


# ---------------------------------------------------------------------------
# GPGGA parsing
# ---------------------------------------------------------------------------

def test_parse_gpgga_valid():
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47"
    result = _parse_gpgga(sentence)
    assert result is not None
    lat, lon, alt = result
    assert lat == pytest.approx(48.0 + 7.038 / 60.0)
    assert alt == pytest.approx(545.4)


def test_parse_gpgga_quality_zero():
    sentence = "$GPGGA,123519,4807.038,N,01131.000,E,0,08,0.9,545.4,M,46.9,M,,*47"
    assert _parse_gpgga(sentence) is None


def test_parse_gpgga_too_short():
    assert _parse_gpgga("$GPGGA,123") is None


# ---------------------------------------------------------------------------
# _parse_nmea_sentences integration
# ---------------------------------------------------------------------------

def test_parse_nmea_sentences_picks_up_gprmc():
    lines = [
        "$GPRMC,123519,A,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A",
    ]
    result = _parse_nmea_sentences(lines)
    assert result is not None
    lat, lon, alt, acc = result


def test_parse_nmea_sentences_returns_none_on_no_fix():
    lines = ["$GPRMC,123519,V,4807.038,N,01131.000,E,022.4,084.4,230394,003.1,W*6A"]
    assert _parse_nmea_sentences(lines) is None


def test_parse_nmea_sentences_empty():
    assert _parse_nmea_sentences([]) is None


# ---------------------------------------------------------------------------
# SpatialCollector (no hardware)
# ---------------------------------------------------------------------------

@pytest.fixture
def collector(tmp_path):
    session = BlackhorseSession()
    signing_key = BHLSigner.generate_key()
    node_id = SpatialPacker.generate_node_id(session.public_key_bytes)
    packer = SpatialPacker(node_id=node_id, signing_key=signing_key, session=session)
    queue = MessageQueue(str(tmp_path / "q.db"))
    col = SpatialCollector(
        node_id=node_id,
        signing_key=signing_key,
        packer=packer,
        queue=queue,
        gps_device="/dev/nonexistent",
        baud=9600,
        poll_interval_seconds=60,
        seq_db_path=":memory:",
    )
    yield col, queue
    col.stop()
    queue.close()


def test_read_gps_returns_none_no_hardware(collector):
    col, _ = collector
    assert col.read_gps() is None


def test_read_sensors_returns_dict(collector):
    col, _ = collector
    result = col.read_sensors()
    assert isinstance(result, dict)


def test_collect_returns_spatial_record(collector):
    col, _ = collector
    record = col.collect()
    assert record is not None
    assert record.node_id == col._node_id
    assert record.latitude == 0.0
    assert record.longitude == 0.0
    assert record.accuracy_m == -1.0


def test_collect_increments_sequence(collector):
    col, _ = collector
    r0 = col.collect()
    r1 = col.collect()
    assert r1.sequence > r0.sequence


def test_background_collection_enqueues(collector):
    col, queue = collector
    col._interval = 0.05  # Very short for testing
    col.start_background_collection()
    time.sleep(0.2)
    col.stop()
    report = queue.status_report()
    assert report["PENDING"] >= 1


def test_stop_terminates_thread(collector):
    col, _ = collector
    col.start_background_collection()
    assert col._bg_thread is not None
    col.stop()
    col._bg_thread.join(timeout=2.0)
    assert not col._bg_thread.is_alive()
