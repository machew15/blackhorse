"""
SIMULATION ONLY — Compression efficiency analysis for modulation research.

Measures how BHL LZ77 compression reduces symbol count and simulated energy
cost when data is pre-processed before modulation symbol encoding.

All energy and efficiency values are RELATIVE SIMULATION UNITS only.
No spectrum, no hardware, no real RF measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List

from blackhorse.compression import compress
from blackhorse.modulation.symbols import ModulationScheme, SymbolMapper


@dataclass
class EfficiencyReport:
    """Result of a single compression-efficiency analysis pass.

    All energy values are simulation units — not real watts or joules.
    This is a relative metric for comparing compressed vs uncompressed data
    under a given modulation scheme. It is NOT real RF performance data.
    """

    input_bytes: int
    compressed_bytes: int
    compression_ratio: float         # input_bytes / compressed_bytes
    scheme: str                      # ModulationScheme name, e.g. "QAM64"
    symbols_uncompressed: int
    symbols_compressed: int
    symbol_reduction_pct: float      # (1 - compressed/uncompressed) * 100
    energy_uncompressed: float       # simulation units (arbitrary, relative)
    energy_compressed: float         # simulation units (arbitrary, relative)
    energy_savings_pct: float        # (1 - compressed/uncompressed energy) * 100
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class EfficiencyAnalyzer:
    """Measures the impact of BHL compression on simulated modulation cost.

    Uses BHL LZ77 compression (``blackhorse.compression.compress``) to
    pre-process data before mapping it through a SymbolMapper. Reports
    the delta in symbol count and simulated energy between raw and
    compressed payloads.

    SIMULATION ONLY — no spectrum, no hardware, no RF.
    """

    def __init__(
        self, scheme: ModulationScheme = ModulationScheme.QAM64
    ) -> None:
        self._scheme = scheme
        self._mapper = SymbolMapper(scheme)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, data: bytes) -> EfficiencyReport:
        """Analyze BHL compression efficiency for *data* under the scheme.

        Steps:
          1. Record raw byte count.
          2. Compress via BHL LZ77 engine.
          3. Map both raw and compressed through the SymbolMapper.
          4. Compute all EfficiencyReport fields.

        Returns a populated EfficiencyReport. All energy values are
        simulation units — relative comparisons only.
        """
        input_bytes = len(data)

        compressed = compress(data)
        compressed_bytes = len(compressed)

        compression_ratio = (
            input_bytes / compressed_bytes if compressed_bytes else float("inf")
        )

        syms_raw = self._mapper.symbol_count(data)
        syms_cmp = self._mapper.symbol_count(compressed)

        reduction_pct = (
            (1.0 - syms_cmp / syms_raw) * 100.0 if syms_raw else 0.0
        )

        energy_raw = self._mapper.energy_estimate(data)
        energy_cmp = self._mapper.energy_estimate(compressed)

        savings_pct = (
            (1.0 - energy_cmp / energy_raw) * 100.0 if energy_raw else 0.0
        )

        return EfficiencyReport(
            input_bytes=input_bytes,
            compressed_bytes=compressed_bytes,
            compression_ratio=round(compression_ratio, 4),
            scheme=self._scheme.name,
            symbols_uncompressed=syms_raw,
            symbols_compressed=syms_cmp,
            symbol_reduction_pct=round(reduction_pct, 2),
            energy_uncompressed=round(energy_raw, 2),
            energy_compressed=round(energy_cmp, 2),
            energy_savings_pct=round(savings_pct, 2),
        )

    def analyze_corpus(self, samples: List[bytes]) -> List[EfficiencyReport]:
        """Run ``analyze()`` on each sample in *samples*.

        Returns a list of EfficiencyReports in the same order as the input.
        Empty corpus returns an empty list.
        """
        return [self.analyze(s) for s in samples]

    def summary(self, reports: List[EfficiencyReport]) -> dict:
        """Aggregate statistics across a list of EfficiencyReports.

        Returns a dict with:
          sample_count, avg_compression_ratio, avg_symbol_reduction_pct,
          avg_energy_savings_pct, best_case_savings_pct, worst_case_savings_pct.

        Returns all-zero values for an empty report list.
        """
        if not reports:
            return {
                "sample_count": 0,
                "avg_compression_ratio": 0.0,
                "avg_symbol_reduction_pct": 0.0,
                "avg_energy_savings_pct": 0.0,
                "best_case_savings_pct": 0.0,
                "worst_case_savings_pct": 0.0,
            }

        n = len(reports)
        savings = [r.energy_savings_pct for r in reports]

        return {
            "sample_count": n,
            "avg_compression_ratio": round(
                sum(r.compression_ratio for r in reports) / n, 4
            ),
            "avg_symbol_reduction_pct": round(
                sum(r.symbol_reduction_pct for r in reports) / n, 2
            ),
            "avg_energy_savings_pct": round(sum(savings) / n, 2),
            "best_case_savings_pct": round(max(savings), 2),
            "worst_case_savings_pct": round(min(savings), 2),
        }
