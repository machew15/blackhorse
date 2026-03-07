"""
Tests for Phase 3 extensions to blackhorse.mesh.detector.

Covers:
- _encode_geohash() determinism and character set
- _encode_geohash() different coords produce different hashes
- _encode_geohash() same coords at different precisions
- get_cluster_diversity() counts distinct geohash prefixes
- get_cluster_diversity() = 1 when all nodes have no geohash
- is_healthy() True when diversity >= min_cluster_diversity
- is_healthy() False when diversity < min_cluster_diversity
- is_healthy() False when not connected
- get_diversity_report() returns expected keys
- rotate_keys() returns non-empty bytes
- generate_node_advertisement() returns signed bytes
"""

import pytest
from datetime import datetime, timezone

from blackhorse.mesh.detector import (
    NodeDetector,
    NodeAdvertisement,
    _encode_geohash,
    generate_node_advertisement,
)
from blackhorse.crypto.signing.hmac_bhl import BHLSigner
from blackhorse.crypto.asymmetric.curve25519 import Curve25519


SIGNING_KEY = BHLSigner.generate_key()


# ---------------------------------------------------------------------------
# Geohash encoding
# ---------------------------------------------------------------------------

_GEOHASH_CHARS = set("0123456789bcdefghjkmnpqrstuvwxyz")


def test_encode_geohash_returns_4_chars():
    gh = _encode_geohash(51.5, -0.1, precision=4)
    assert len(gh) == 4


def test_encode_geohash_valid_chars():
    gh = _encode_geohash(40.71, -74.00, precision=4)
    assert all(c in _GEOHASH_CHARS for c in gh)


def test_encode_geohash_deterministic():
    gh1 = _encode_geohash(51.5, -0.1)
    gh2 = _encode_geohash(51.5, -0.1)
    assert gh1 == gh2


def test_encode_geohash_different_coords_different_hash():
    gh_london = _encode_geohash(51.5, -0.1)
    gh_sydney = _encode_geohash(-33.8, 151.2)
    assert gh_london != gh_sydney


def test_encode_geohash_precision_prefix():
    gh4 = _encode_geohash(51.5, -0.1, precision=4)
    gh6 = _encode_geohash(51.5, -0.1, precision=6)
    # 6-char hash should start with the 4-char prefix
    assert gh6.startswith(gh4)


def test_encode_geohash_north_south():
    # Northern hemisphere vs southern hemisphere
    north = _encode_geohash(50.0, 10.0)
    south = _encode_geohash(-50.0, 10.0)
    assert north != south


# ---------------------------------------------------------------------------
# NodeDetector spatial diversity
# ---------------------------------------------------------------------------

def _make_node(node_id: str, geohash: str | None = None) -> NodeAdvertisement:
    node = NodeAdvertisement(
        node_id=node_id,
        address="10.0.0.1",
        last_seen=datetime.now(timezone.utc),
    )
    node.geohash = geohash
    return node


def test_get_cluster_diversity_no_nodes():
    detector = NodeDetector(scan_interval_seconds=30)
    assert detector.get_cluster_diversity() == 0


def test_get_cluster_diversity_single_cluster():
    detector = NodeDetector(scan_interval_seconds=30)
    detector.register_node(_make_node("n1", geohash="gcpv"))
    detector.register_node(_make_node("n2", geohash="gcpv"))
    assert detector.get_cluster_diversity() == 1


def test_get_cluster_diversity_two_clusters():
    detector = NodeDetector(scan_interval_seconds=30)
    detector.register_node(_make_node("n1", geohash="gcpv"))
    detector.register_node(_make_node("n2", geohash="u10h"))
    assert detector.get_cluster_diversity() == 2


def test_get_cluster_diversity_no_geohash_single_bucket():
    detector = NodeDetector(scan_interval_seconds=30)
    detector.register_node(_make_node("n1", geohash=None))
    detector.register_node(_make_node("n2", geohash=None))
    # Both go into "__no_geo__" bucket — still 1 cluster
    assert detector.get_cluster_diversity() == 1


def test_is_healthy_false_when_not_connected():
    detector = NodeDetector(scan_interval_seconds=30, min_cluster_diversity=1)
    assert not detector.is_healthy()


def test_is_healthy_false_when_low_diversity():
    detector = NodeDetector(scan_interval_seconds=30, min_cluster_diversity=3)
    detector.register_node(_make_node("n1", geohash="gcpv"))
    detector.register_node(_make_node("n2", geohash="gcpv"))
    assert not detector.is_healthy()


def test_is_healthy_true_when_sufficient_diversity():
    detector = NodeDetector(scan_interval_seconds=30, min_cluster_diversity=2)
    detector.register_node(_make_node("n1", geohash="gcpv"))
    detector.register_node(_make_node("n2", geohash="u10h"))
    assert detector.is_healthy()


def test_get_diversity_report_keys():
    detector = NodeDetector(scan_interval_seconds=30)
    report = detector.get_diversity_report()
    assert "total_nodes" in report
    assert "distinct_clusters" in report
    assert "cluster_ids" in report
    assert "is_healthy" in report


def test_get_diversity_report_correct_counts():
    detector = NodeDetector(scan_interval_seconds=30, min_cluster_diversity=2)
    detector.register_node(_make_node("n1", geohash="aaaa"))
    detector.register_node(_make_node("n2", geohash="bbbb"))
    report = detector.get_diversity_report()
    assert report["total_nodes"] == 2
    assert report["distinct_clusters"] == 2
    assert report["is_healthy"] is True


# ---------------------------------------------------------------------------
# Key rotation and generate_node_advertisement
# ---------------------------------------------------------------------------

def test_generate_node_advertisement_returns_bytes():
    kp = Curve25519.generate()
    advert = generate_node_advertisement(kp.public_key_bytes, SIGNING_KEY)
    assert isinstance(advert, bytes)
    assert len(advert) > 0


def test_generate_node_advertisement_different_keys():
    kp1 = Curve25519.generate()
    kp2 = Curve25519.generate()
    a1 = generate_node_advertisement(kp1.public_key_bytes, SIGNING_KEY)
    a2 = generate_node_advertisement(kp2.public_key_bytes, SIGNING_KEY)
    assert a1 != a2


def test_rotate_keys_returns_bytes():
    detector = NodeDetector()
    kp = Curve25519.generate()
    result = detector.rotate_keys((kp.public_key_bytes, b"\x00" * 32), SIGNING_KEY)
    assert isinstance(result, bytes)
    assert len(result) > 0
