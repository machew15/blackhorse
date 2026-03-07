"""
Tests for blackhorse.mesh.cli — argparse CLI.

Covers:
- build_parser() returns a valid ArgumentParser
- status command with empty components doesn't crash
- report command with ledger prints text
- report --geojson outputs GeoJSON
- trust command prints trust info
- policy command prints policy info
- flush command calls flusher.flush()
- unknown command exits with error
"""

import io
import sys
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from blackhorse.mesh.cli import build_parser, main
from blackhorse.mesh.flusher import FlushReport


@pytest.fixture
def empty_components():
    return {}


@pytest.fixture
def full_components(tmp_path):
    from blackhorse.mesh.queue import MessageQueue
    from blackhorse.mesh.detector import NodeDetector
    from blackhorse.mesh.ledger import ContributionLedger
    from blackhorse.mesh.parameters import ParticipationPolicy, PolicyConfig
    from blackhorse.mesh.registry import SpatialRegistry

    queue = MessageQueue(str(tmp_path / "q.db"))
    detector = NodeDetector()
    ledger = ContributionLedger(str(tmp_path / "ledger.db"))
    policy = ParticipationPolicy(config=PolicyConfig(), ledger=ledger)
    registry = SpatialRegistry(str(tmp_path / "reg.db"))

    mock_flusher = MagicMock()
    mock_flusher.flush.return_value = FlushReport(
        attempted=3, acknowledged=2, failed=1,
        timestamp=datetime.now(timezone.utc),
    )

    return {
        "queue": queue,
        "detector": detector,
        "ledger": ledger,
        "policy": policy,
        "registry": registry,
        "flusher": mock_flusher,
        "node_id": "a" * 64,
    }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def test_build_parser_returns_parser():
    parser = build_parser()
    assert parser is not None


def test_parser_requires_command():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_parser_status_command():
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.command == "status"


def test_parser_trust_command():
    parser = build_parser()
    args = parser.parse_args(["trust", "abc123"])
    assert args.command == "trust"
    assert args.node_id == "abc123"


def test_parser_report_geojson_flag():
    parser = build_parser()
    args = parser.parse_args(["report", "--geojson"])
    assert args.geojson is True


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_runs_without_crash(full_components, capsys):
    main(argv=["status"], components=full_components)
    out = capsys.readouterr().out
    assert "BLACKHORSE" in out
    assert "NODE STATUS" in out


def test_status_with_empty_components_does_not_crash(empty_components, capsys):
    main(argv=["status"], components=empty_components)
    out = capsys.readouterr().out
    assert "BLACKHORSE" in out


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def test_report_prints_ledger(full_components, capsys):
    main(argv=["report"], components=full_components)
    out = capsys.readouterr().out
    assert "CONTRIBUTION" in out or "BLACKHORSE" in out


def test_report_geojson_outputs_geojson(full_components, capsys):
    main(argv=["report", "--geojson"], components=full_components)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["type"] == "FeatureCollection"


def test_report_geojson_missing_registry_exits(empty_components):
    with pytest.raises(SystemExit):
        main(argv=["report", "--geojson"], components=empty_components)


# ---------------------------------------------------------------------------
# trust
# ---------------------------------------------------------------------------

def test_trust_command_output(full_components, capsys):
    main(argv=["trust", "a" * 64], components=full_components)
    out = capsys.readouterr().out
    assert "TRUST REPORT" in out
    assert "Trust score" in out


def test_trust_command_missing_ledger_exits(empty_components):
    with pytest.raises(SystemExit):
        main(argv=["trust", "some-node"], components=empty_components)


# ---------------------------------------------------------------------------
# policy
# ---------------------------------------------------------------------------

def test_policy_command_output(full_components, capsys):
    main(argv=["policy"], components=full_components)
    out = capsys.readouterr().out
    assert "POLICY" in out
    assert "max_bytes_per_relay" in out


def test_policy_missing_policy_exits(empty_components):
    with pytest.raises(SystemExit):
        main(argv=["policy"], components=empty_components)


# ---------------------------------------------------------------------------
# flush
# ---------------------------------------------------------------------------

def test_flush_command_calls_flusher(full_components, capsys):
    main(argv=["flush"], components=full_components)
    full_components["flusher"].flush.assert_called_once()
    out = capsys.readouterr().out
    assert "MANUAL FLUSH" in out
    assert "Attempted" in out


def test_flush_missing_flusher_exits(empty_components):
    with pytest.raises(SystemExit):
        main(argv=["flush"], components=empty_components)
