"""
Tests for blackhorse.mesh.spatial — SpatialRecord, SpatialPacker, ReplayError.

Covers:
- SpatialRecord.to_dict() / from_dict() round-trip
- has_gps_fix() True/False logic
- generate_node_id() determinism
- pack() → unpack() round-trip
- SigningError on tampered packet
- ReplayError when sequence is not strictly increasing
- ReplayError on duplicate sequence
"""

import pytest

from blackhorse.interface.handshake import BlackhorseSession
from blackhorse.crypto.signing.hmac_bhl import BHLSigner, SigningError
from blackhorse.mesh.spatial import SpatialRecord, SpatialPacker, ReplayError
from datetime import datetime, timezone


SIGNING_KEY = BHLSigner.generate_key()


@pytest.fixture
def session():
    return BlackhorseSession()


@pytest.fixture
def packer(session):
    node_id = SpatialPacker.generate_node_id(session.public_key_bytes)
    return SpatialPacker(node_id=node_id, signing_key=SIGNING_KEY, session=session)


def _make_record(node_id: str, seq: int, lat: float = 51.5, lon: float = -0.1) -> SpatialRecord:
    return SpatialRecord(
        node_id=node_id,
        latitude=lat,
        longitude=lon,
        altitude_m=10.0,
        accuracy_m=5.0,
        timestamp=datetime.now(timezone.utc),
        sensor_data={"temp_c": 22.5},
        sequence=seq,
    )


# ---------------------------------------------------------------------------
# SpatialRecord
# ---------------------------------------------------------------------------

def test_record_to_dict_from_dict_round_trip():
    record = _make_record("node123", seq=1)
    d = record.to_dict()
    restored = SpatialRecord.from_dict(d)
    assert restored.node_id == record.node_id
    assert restored.latitude == record.latitude
    assert restored.longitude == record.longitude
    assert restored.sequence == record.sequence
    assert restored.sensor_data == record.sensor_data


def test_has_gps_fix_true():
    record = _make_record("n", 0, lat=51.5, lon=-0.1)
    assert record.has_gps_fix()


def test_has_gps_fix_false_zero_coords():
    record = _make_record("n", 0, lat=0.0, lon=0.0)
    assert not record.has_gps_fix()


def test_has_gps_fix_false_negative_accuracy():
    record = SpatialRecord(
        node_id="n", latitude=51.5, longitude=-0.1,
        altitude_m=0.0, accuracy_m=-1.0,
        timestamp=datetime.now(timezone.utc),
        sensor_data={}, sequence=0,
    )
    assert not record.has_gps_fix()


# ---------------------------------------------------------------------------
# SpatialPacker
# ---------------------------------------------------------------------------

def test_generate_node_id_is_hex_sha256():
    pub = b"\x42" * 32
    node_id = SpatialPacker.generate_node_id(pub)
    assert len(node_id) == 64
    assert all(c in "0123456789abcdef" for c in node_id)


def test_generate_node_id_is_deterministic():
    pub = b"\x99" * 32
    assert SpatialPacker.generate_node_id(pub) == SpatialPacker.generate_node_id(pub)


def test_pack_returns_bytes(packer):
    record = _make_record(packer._node_id, seq=0)
    packed = packer.pack(record)
    assert isinstance(packed, bytes)
    assert len(packed) > 0


def test_pack_unpack_round_trip(packer):
    record = _make_record(packer._node_id, seq=0)
    packed = packer.pack(record)
    restored = packer.unpack(packed, SIGNING_KEY)
    assert restored.node_id == record.node_id
    assert abs(restored.latitude - record.latitude) < 1e-6
    assert restored.sequence == record.sequence
    assert restored.sensor_data == record.sensor_data


def test_unpack_raises_signing_error_on_tampered(packer):
    record = _make_record(packer._node_id, seq=10)
    packed = packer.pack(record)
    tampered = bytearray(packed)
    tampered[-5] ^= 0xFF
    with pytest.raises(SigningError):
        packer.unpack(bytes(tampered), SIGNING_KEY)


def test_unpack_raises_replay_error_on_old_sequence(packer):
    record0 = _make_record(packer._node_id, seq=5)
    record1 = _make_record(packer._node_id, seq=3)
    packer.unpack(packer.pack(record0), SIGNING_KEY)
    with pytest.raises(ReplayError):
        packer.unpack(packer.pack(record1), SIGNING_KEY)


def test_unpack_raises_replay_error_on_duplicate_sequence(packer):
    record = _make_record(packer._node_id, seq=7)
    packer.unpack(packer.pack(record), SIGNING_KEY)
    with pytest.raises(ReplayError):
        packer.unpack(packer.pack(record), SIGNING_KEY)


def test_unpack_accepts_strictly_increasing_sequences(packer):
    for seq in [0, 1, 5, 100]:
        record = _make_record(packer._node_id, seq=seq)
        result = packer.unpack(packer.pack(record), SIGNING_KEY)
        assert result.sequence == seq
