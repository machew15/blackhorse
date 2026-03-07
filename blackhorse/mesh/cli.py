"""
Phase 3E — Operator CLI.

Plain-text, 80-column, argparse-only command-line interface for Blackhorse Mesh
operators. Designed for Raspberry Pi terminals with no colour support assumed.

Usage:
  python -m blackhorse.mesh.cli status
  python -m blackhorse.mesh.cli report [--geojson]
  python -m blackhorse.mesh.cli trust <node_id>
  python -m blackhorse.mesh.cli policy
  python -m blackhorse.mesh.cli flush
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

_LINE = "=" * 78
_DASH = "-" * 78


def _fmt(label: str, value: object, width: int = 30) -> str:
    """Format a label-value pair for 80-column display."""
    return f"  {label:<{width}} {value}"


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def _cmd_status(args: argparse.Namespace, components: dict) -> None:
    """Print a compact status summary for the local node."""
    queue = components.get("queue")
    detector = components.get("detector")
    registry = components.get("registry")
    ledger = components.get("ledger")
    policy = components.get("policy")
    node_id = components.get("node_id", "unknown")

    print(_LINE)
    print("  BLACKHORSE MESH — NODE STATUS")
    print(_LINE)
    print(_fmt("Node ID:", node_id[:32] + "..."))
    print(_fmt("Generated at:", datetime.now(timezone.utc).isoformat()))

    if detector is not None:
        connected = detector.is_connected()
        healthy = detector.is_healthy() if hasattr(detector, "is_healthy") else "n/a"
        live = len(detector.get_available_nodes())
        print(_fmt("Connected:", "YES" if connected else "NO"))
        print(_fmt("Network healthy:", str(healthy)))
        print(_fmt("Live nodes:", live))
    else:
        print(_fmt("Detector:", "not configured"))

    print(_DASH)
    if queue is not None:
        report = queue.status_report()
        print("  QUEUE")
        for status, count in sorted(report.items()):
            print(_fmt(f"  {status}:", count, width=28))
    else:
        print(_fmt("Queue:", "not configured"))

    print(_DASH)
    if registry is not None:
        print(_fmt("Known nodes (registry):", registry.node_count()))
    else:
        print(_fmt("Registry:", "not configured"))

    print(_DASH)
    if ledger is not None:
        top = ledger.top_contributors(limit=5)
        print("  TOP CONTRIBUTORS (up to 5)")
        if top:
            for i, c in enumerate(top, 1):
                nid = c["node_id"][:16]
                score = f"{c['trust_score']:.3f}"
                print(f"  {i:2d}. {nid}...  relays={c['given']:5d}  trust={score}")
        else:
            print("  (no contributions yet)")
    else:
        print(_fmt("Ledger:", "not configured"))

    print(_DASH)
    if policy is not None:
        report = policy.get_policy_report()
        cfg = report["config"]
        print("  POLICY SUMMARY")
        print(_fmt("  Max bytes/relay:", cfg["max_bytes_per_relay"]))
        print(_fmt("  Max relays/hour:", cfg["max_relays_per_hour"]))
        print(_fmt("  Max queue size:", cfg["max_queue_size"]))
        print(_fmt("  Min trust score:", cfg["min_trust_score"]))
    else:
        print(_fmt("Policy:", "not configured"))

    print(_LINE)


def _cmd_report(args: argparse.Namespace, components: dict) -> None:
    """Print the full ledger report, or GeoJSON if --geojson is set."""
    if getattr(args, "geojson", False):
        registry = components.get("registry")
        if registry is None:
            print("ERROR: registry not configured", file=sys.stderr)
            sys.exit(1)
        print(registry.export_geojson())
        return

    ledger = components.get("ledger")
    if ledger is None:
        print("ERROR: ledger not configured", file=sys.stderr)
        sys.exit(1)
    print(ledger.export_report())


def _cmd_trust(args: argparse.Namespace, components: dict) -> None:
    """Print trust score and contribution summary for a given node_id."""
    ledger = components.get("ledger")
    if ledger is None:
        print("ERROR: ledger not configured", file=sys.stderr)
        sys.exit(1)

    node_id: str = args.node_id
    score = ledger.get_trust_score(node_id)
    summary = ledger.get_node_contributions(node_id)

    print(_LINE)
    print(f"  TRUST REPORT — {node_id[:32]}...")
    print(_LINE)
    print(_fmt("Trust score:", f"{score:.4f}"))
    print(_fmt("Relays given:", summary["given"]))
    print(_fmt("Relays received:", summary["received"]))
    print(_fmt("Bytes given:", summary["bytes_given"]))
    print(_fmt("Bytes received:", summary["bytes_received"]))
    print(_fmt("First seen:", summary["first_seen"] or "never"))
    print(_fmt("Last seen:", summary["last_seen"] or "never"))
    print(_LINE)


def _cmd_policy(args: argparse.Namespace, components: dict) -> None:
    """Print the current ParticipationPolicy configuration."""
    policy = components.get("policy")
    if policy is None:
        print("ERROR: policy not configured", file=sys.stderr)
        sys.exit(1)

    report = policy.get_policy_report()
    cfg = report["config"]

    print(_LINE)
    print("  PARTICIPATION POLICY — CURRENT CONFIGURATION")
    print(_LINE)
    for key, value in cfg.items():
        print(_fmt(f"  {key}:", value))
    print(_DASH)
    hourly = report["hourly_relay_counts"]
    print("  HOURLY RELAY COUNTS (last 60 minutes)")
    if hourly:
        for nid, count in sorted(hourly.items(), key=lambda x: -x[1])[:10]:
            print(f"  {nid[:24]}...  {count:5d}")
    else:
        print("  (no relays recorded)")
    print(_LINE)


def _cmd_flush(args: argparse.Namespace, components: dict) -> None:
    """Manually trigger a queue flush and print the FlushReport."""
    flusher = components.get("flusher")
    if flusher is None:
        print("ERROR: flusher not configured", file=sys.stderr)
        sys.exit(1)

    print(_LINE)
    print("  MANUAL FLUSH")
    print(_LINE)
    print("  Flushing queue...")

    report = flusher.flush()

    print(_fmt("  Attempted:", report.attempted))
    print(_fmt("  Acknowledged:", report.acknowledged))
    print(_fmt("  Failed:", report.failed))
    print(_fmt("  Completed at:", report.timestamp.isoformat()))
    print(_LINE)


# ---------------------------------------------------------------------------
# Parser factory (importable for testing)
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="blackhorse-mesh",
        description="Blackhorse Mesh operator CLI — 80-column plain text output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Node status, queue summary, top contributors")

    report_p = sub.add_parser("report", help="Full ledger report")
    report_p.add_argument(
        "--geojson",
        action="store_true",
        help="Output registry GeoJSON to stdout instead of ledger report",
    )

    trust_p = sub.add_parser("trust", help="Trust score for a specific node")
    trust_p.add_argument("node_id", help="Hex node_id to look up")

    sub.add_parser("policy", help="Current participation policy configuration")
    sub.add_parser("flush", help="Manually trigger queue flush")

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None, components: dict | None = None) -> None:
    """
    Main CLI entry point.

    Parameters
    ----------
    argv       : Argument list (defaults to sys.argv[1:]).
    components : Dict of runtime objects: queue, detector, registry, ledger,
                 policy, flusher, node_id. Pass None to get usage-only mode.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    comps = components or {}

    dispatch = {
        "status": _cmd_status,
        "report": _cmd_report,
        "trust": _cmd_trust,
        "policy": _cmd_policy,
        "flush": _cmd_flush,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(1)

    fn(args, comps)


if __name__ == "__main__":
    main()
