"""
SIMULATION ONLY — Orchestrates the full modulation simulation pipeline.

SimulationRunner connects compression analysis, governance policy, and
media attestation into a single callable interface. All outputs are clearly
labeled as simulation data — not real RF measurements, not real spectrum use.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from blackhorse.modulation.analyzer import EfficiencyAnalyzer, EfficiencyReport
from blackhorse.modulation.governance import (
    GovernedOutput,
    ModulationPolicy,
)
from blackhorse.modulation.symbols import ModulationScheme


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SimulationResult:
    """Aggregate result of a corpus simulation run.

    SIMULATION ONLY — all energy and efficiency values are relative
    simulation units, not real RF measurements.
    """

    corpus_name: str
    sample_count: int
    scheme: str
    summary: dict
    governed_outputs: List[GovernedOutput]
    signed_report: Optional[bytes] = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ComparisonResult:
    """Per-scheme efficiency comparison for a single text sample.

    SIMULATION ONLY — not real RF data.
    """

    input_text: str
    results: Dict[str, GovernedOutput]   # scheme name → GovernedOutput
    most_efficient_scheme: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class MediaSimulationResult:
    """Result of a synthetic media corpus simulation run.

    Tracks how many items required human approval (video), were approved
    automatically, or were rejected by policy.

    SIMULATION ONLY — no real media transmitted.
    """

    reports: list   # list[MediaEfficiencyReport]
    video_blocked_count: int
    approved_count: int
    rejected_count: int
    summary: dict
    signed_result: Optional[bytes] = None
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ---------------------------------------------------------------------------
# SimulationRunner
# ---------------------------------------------------------------------------


class SimulationRunner:
    """Orchestrates the end-to-end modulation simulation pipeline.

    Connects:
      - EfficiencyAnalyzer  — measures compression impact on symbol count
      - ModulationPolicy    — enforces parametric governance constraints
      - Optional signing    — signs result packets for verifiable attestation

    SIMULATION ONLY — no RF, no spectrum, no hardware.
    """

    def __init__(
        self,
        policy: ModulationPolicy,
        analyzer: EfficiencyAnalyzer,
        signing_key: Optional[bytes] = None,
    ) -> None:
        self._policy = policy
        self._analyzer = analyzer
        self._signing_key = signing_key

    # ------------------------------------------------------------------
    # Single-sample runs
    # ------------------------------------------------------------------

    def run_text_sample(
        self, text: str, scheme: ModulationScheme
    ) -> GovernedOutput:
        """Encode *text* to UTF-8 and run it through the full pipeline.

        Returns a GovernedOutput carrying the efficiency report, policy
        verdict, optional attestation, and education note.
        """
        data = text.encode("utf-8")
        report = self._analyzer.analyze(data)
        return self._policy.apply(data, scheme, report)

    def run_file(self, filepath: str) -> object:
        """Analyze a local file and return a MediaEfficiencyReport.

        SIMULATION ONLY — reads locally, does NOT transmit or upload.
        Prints a clear notice before running.
        """
        print(
            "SIMULATION — file analyzed locally, not transmitted: "
            + filepath
        )
        from blackhorse.modulation.media_analyzer import (  # noqa: PLC0415
            MediaEfficiencyAnalyzer,
        )

        if not isinstance(self._analyzer, MediaEfficiencyAnalyzer):
            raise TypeError(
                "run_file() requires a MediaEfficiencyAnalyzer instance."
            )
        return self._analyzer.analyze_file(filepath)

    # ------------------------------------------------------------------
    # Corpus runs
    # ------------------------------------------------------------------

    def run_institutional_corpus(
        self,
        texts: List[str],
        scheme: ModulationScheme,
        corpus_name: str = "institutional_corpus",
    ) -> SimulationResult:
        """Run the full pipeline over a corpus of text samples.

        Designed for Fed transcripts, congressional text, policy documents.
        Handles an empty corpus gracefully (returns zero-summary result).

        Returns a SimulationResult with aggregate statistics.
        """
        if not texts:
            return SimulationResult(
                corpus_name=corpus_name,
                sample_count=0,
                scheme=scheme.name,
                summary=self._analyzer.summary([]),
                governed_outputs=[],
            )

        governed_outputs: List[GovernedOutput] = []
        reports: List[EfficiencyReport] = []

        for text in texts:
            data = text.encode("utf-8")
            report = self._analyzer.analyze(data)
            reports.append(report)
            try:
                gov = self._policy.apply(data, scheme, report)
            except Exception:
                gov = GovernedOutput(report=report, policy_approved=False)
            governed_outputs.append(gov)

        summary = self._analyzer.summary(reports)

        signed_report: Optional[bytes] = None
        if self._signing_key:
            import json  # noqa: PLC0415
            from blackhorse.crypto.signing import BHLSigner  # noqa: PLC0415

            payload = json.dumps(
                {
                    "corpus_name": corpus_name,
                    "scheme": scheme.name,
                    "summary": summary,
                },
                separators=(",", ":"),
            ).encode()
            signed_report = BHLSigner().sign(payload, self._signing_key)

        return SimulationResult(
            corpus_name=corpus_name,
            sample_count=len(texts),
            scheme=scheme.name,
            summary=summary,
            governed_outputs=governed_outputs,
            signed_report=signed_report,
        )

    # ------------------------------------------------------------------
    # Scheme comparison
    # ------------------------------------------------------------------

    def run_comparison(self, text: str) -> ComparisonResult:
        """Run *text* through all four ModulationSchemes and compare results.

        Returns a ComparisonResult showing efficiency across schemes and
        identifying the most energy-efficient option.
        """
        data = text.encode("utf-8")
        results: Dict[str, GovernedOutput] = {}
        best_scheme = ""
        best_savings = float("-inf")

        for scheme in ModulationScheme:
            report = self._analyzer.analyze(data)
            try:
                gov = self._policy.apply(data, scheme, report)
            except Exception:
                gov = GovernedOutput(report=report, policy_approved=False)
            results[scheme.name] = gov

            if gov.report.energy_savings_pct > best_savings:
                best_savings = gov.report.energy_savings_pct
                best_scheme = scheme.name

        return ComparisonResult(
            input_text=text,
            results=results,
            most_efficient_scheme=best_scheme,
        )

    # ------------------------------------------------------------------
    # Media simulation
    # ------------------------------------------------------------------

    def run_media_simulation(self) -> MediaSimulationResult:
        """Run a synthetic media corpus through the full pipeline.

        Uses MediaEfficiencyAnalyzer.simulate_media_corpus() to generate
        one synthetic sample per MediaType and analyze each.

        Tracks video-blocked count, approved count, and rejected count.
        Returns a MediaSimulationResult with provenance hashes per type.

        SIMULATION ONLY — no real media, no transmission.
        """
        from blackhorse.modulation.media_analyzer import (  # noqa: PLC0415
            MediaEfficiencyAnalyzer,
            MediaEfficiencyReport,
        )

        if not isinstance(self._analyzer, MediaEfficiencyAnalyzer):
            raise TypeError(
                "run_media_simulation() requires a MediaEfficiencyAnalyzer."
            )

        reports: list[MediaEfficiencyReport] = (
            self._analyzer.simulate_media_corpus()
        )

        video_blocked = sum(
            1 for r in reports if "VIDEO_REQUIRES_HUMAN_APPROVAL" in r.governance_note
        )
        approved = sum(1 for r in reports if "APPROVED" in r.governance_note)
        rejected = len(reports) - approved

        # Build a lightweight summary from base fields.
        base_reports = [r for r in reports]  # type: ignore[assignment]
        summary = {
            "sample_count": len(reports),
            "avg_compression_ratio": round(
                sum(r.compression_ratio for r in reports) / len(reports), 4
            ) if reports else 0.0,
            "avg_energy_savings_pct": round(
                sum(r.energy_savings_pct for r in reports) / len(reports), 2
            ) if reports else 0.0,
        }

        signed_result: Optional[bytes] = None
        if self._signing_key:
            import json  # noqa: PLC0415
            from blackhorse.crypto.signing import BHLSigner  # noqa: PLC0415

            payload = json.dumps(
                {
                    "type": "MEDIA_SIMULATION_RESULT",
                    "video_blocked": video_blocked,
                    "approved": approved,
                    "rejected": rejected,
                    "summary": summary,
                },
                separators=(",", ":"),
            ).encode()
            signed_result = BHLSigner().sign(payload, self._signing_key)

        return MediaSimulationResult(
            reports=reports,
            video_blocked_count=video_blocked,
            approved_count=approved,
            rejected_count=rejected,
            summary=summary,
            signed_result=signed_result,
        )


# ---------------------------------------------------------------------------
# print_report — 80-column human-readable output
# ---------------------------------------------------------------------------

_WIDTH = 79
_LINE = "═" * _WIDTH
_THIN = "─" * _WIDTH


def _center(text: str, width: int = _WIDTH) -> str:
    return text.center(width)


def _wrap(text: str, indent: int = 2) -> str:
    prefix = " " * indent
    return "\n".join(
        textwrap.fill(line, width=_WIDTH, initial_indent=prefix,
                      subsequent_indent=prefix)
        for line in text.splitlines()
    )


def print_report(result: object) -> None:
    """Print a human-readable summary of a SimulationResult or ComparisonResult.

    80-column formatted. Clearly labels everything as SIMULATION data.
    No external libraries required.
    """
    from blackhorse.modulation.runner import (  # noqa: PLC0415
        ComparisonResult,
        MediaSimulationResult,
        SimulationResult,
    )

    if isinstance(result, SimulationResult):
        _print_simulation_result(result)
    elif isinstance(result, ComparisonResult):
        _print_comparison_result(result)
    elif isinstance(result, MediaSimulationResult):
        _print_media_simulation_result(result)
    else:
        print(f"[print_report] Unknown result type: {type(result)}")


def _print_simulation_result(result: SimulationResult) -> None:
    s = result.summary
    print(_LINE)
    print(_center("BLACKHORSE MODULATION SIMULATION — CORPUS REPORT"))
    print(_center("SIMULATION ONLY — NOT REAL RF DATA"))
    print(_THIN)
    print(f"  Corpus       : {result.corpus_name}")
    print(f"  Scheme       : {result.scheme}")
    print(f"  Samples      : {result.sample_count}")
    print(f"  Timestamp    : {result.timestamp.isoformat()}")
    print(_THIN)
    print("  AGGREGATE EFFICIENCY SUMMARY")
    print(_THIN)
    print(f"  Avg compression ratio     : {s.get('avg_compression_ratio', 0):.4f}×")
    print(f"  Avg symbol reduction      : {s.get('avg_symbol_reduction_pct', 0):.2f}%")
    print(f"  Avg energy savings        : {s.get('avg_energy_savings_pct', 0):.2f}%")
    print(f"  Best-case energy savings  : {s.get('best_case_savings_pct', 0):.2f}%")
    print(f"  Worst-case energy savings : {s.get('worst_case_savings_pct', 0):.2f}%")
    if result.signed_report:
        print(_THIN)
        print(f"  Signed report : {len(result.signed_report)} bytes (HMAC-SHA256)")
    print(_LINE)


def _print_comparison_result(result: ComparisonResult) -> None:
    preview = result.input_text[:60].replace("\n", " ")
    print(_LINE)
    print(_center("BLACKHORSE MODULATION SIMULATION — SCHEME COMPARISON"))
    print(_center("SIMULATION ONLY — NOT REAL RF DATA"))
    print(_THIN)
    print(f"  Input (first 60 chars): {preview!r}")
    print(f"  Timestamp             : {result.timestamp.isoformat()}")
    print(_THIN)
    print(
        f"  {'Scheme':<8}  {'Syms-Raw':>9}  {'Syms-Cmp':>9}  "
        f"{'Sym-Red%':>8}  {'E-Save%':>8}  {'Status'}"
    )
    print("  " + "─" * 65)
    for scheme_name, gov in result.results.items():
        r = gov.report
        status = "APPROVED" if gov.policy_approved else "BLOCKED"
        print(
            f"  {scheme_name:<8}  {r.symbols_uncompressed:>9,}  "
            f"{r.symbols_compressed:>9,}  {r.symbol_reduction_pct:>7.2f}%  "
            f"{r.energy_savings_pct:>7.2f}%  {status}"
        )
    print(_THIN)
    print(f"  Most energy-efficient scheme: {result.most_efficient_scheme}")
    print(_LINE)


def _print_media_simulation_result(result: MediaSimulationResult) -> None:
    print(_LINE)
    print(_center("BLACKHORSE MODULATION SIMULATION — MEDIA CORPUS"))
    print(_center("SIMULATION ONLY — NO REAL MEDIA TRANSMITTED"))
    print(_THIN)
    print(f"  Total reports : {len(result.reports)}")
    print(f"  Approved      : {result.approved_count}")
    print(f"  Rejected      : {result.rejected_count}")
    print(f"  Video blocked : {result.video_blocked_count}  "
          "(require human approval via MediaAttestor.approve())")
    print(_THIN)
    print(f"  {'Type':<12}  {'Size(B)':>9}  {'Cmp(B)':>9}  "
          f"{'Ratio':>7}  {'E-Save%':>8}  {'Hash (first 16)'}")
    print("  " + "─" * 73)
    for r in result.reports:
        h = r.content_hash[:16] if r.content_hash else "n/a"
        print(
            f"  {r.media_type:<12}  {r.input_bytes:>9,}  "
            f"{r.compressed_bytes:>9,}  {r.compression_ratio:>7.3f}×  "
            f"{r.energy_savings_pct:>7.2f}%  {h}"
        )
    if result.signed_result:
        print(_THIN)
        print(f"  Signed result : {len(result.signed_result)} bytes (HMAC-SHA256)")
    print(_LINE)
