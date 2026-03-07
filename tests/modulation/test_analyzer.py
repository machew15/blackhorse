"""Tests for blackhorse.modulation.analyzer — SIMULATION ONLY."""

import pytest

from blackhorse.modulation.analyzer import EfficiencyAnalyzer, EfficiencyReport
from blackhorse.modulation.samples import (
    SAMPLE_INSTITUTIONAL_TEXT,
    SAMPLE_MESH_MESSAGES,
    SAMPLE_SENSOR_DATA,
)
from blackhorse.modulation.symbols import ModulationScheme


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def analyzer():
    return EfficiencyAnalyzer(scheme=ModulationScheme.QAM64)


@pytest.fixture
def all_samples_bytes():
    texts = SAMPLE_INSTITUTIONAL_TEXT + SAMPLE_SENSOR_DATA + SAMPLE_MESH_MESSAGES
    return [t.encode("utf-8") for t in texts]


# ---------------------------------------------------------------------------
# EfficiencyReport — field validity
# ---------------------------------------------------------------------------


class TestEfficiencyReport:
    def test_analyze_returns_efficiency_report(self, analyzer):
        report = analyzer.analyze(b"hello world simulation data")
        assert isinstance(report, EfficiencyReport)

    def test_compression_ratio_positive(self, analyzer):
        for text in SAMPLE_INSTITUTIONAL_TEXT:
            report = analyzer.analyze(text.encode("utf-8"))
            assert report.compression_ratio > 0, (
                "compression_ratio must always be positive"
            )

    def test_input_bytes_matches_data_length(self, analyzer):
        data = b"test payload for simulation"
        report = analyzer.analyze(data)
        assert report.input_bytes == len(data)

    def test_compressed_bytes_positive(self, analyzer):
        report = analyzer.analyze(b"some data to compress")
        assert report.compressed_bytes > 0

    def test_scheme_name_correct(self, analyzer):
        report = analyzer.analyze(b"data")
        assert report.scheme == "QAM64"

    @pytest.mark.parametrize("scheme", list(ModulationScheme))
    def test_scheme_name_reflects_scheme(self, scheme):
        a = EfficiencyAnalyzer(scheme=scheme)
        report = a.analyze(b"test data for all schemes")
        assert report.scheme == scheme.name

    def test_symbol_counts_positive(self, analyzer):
        report = analyzer.analyze(b"symbol count test")
        assert report.symbols_uncompressed > 0
        assert report.symbols_compressed > 0

    def test_symbol_reduction_in_valid_range(self, analyzer):
        """symbol_reduction_pct must be in [-100, 100] for any payload."""
        for text in SAMPLE_INSTITUTIONAL_TEXT:
            report = analyzer.analyze(text.encode("utf-8"))
            assert -100.0 <= report.symbol_reduction_pct <= 100.0

    def test_energy_values_positive(self, analyzer):
        report = analyzer.analyze(b"energy estimate test")
        assert report.energy_uncompressed > 0
        assert report.energy_compressed > 0

    def test_energy_savings_in_valid_range(self, analyzer):
        for text in SAMPLE_INSTITUTIONAL_TEXT:
            report = analyzer.analyze(text.encode("utf-8"))
            assert -200.0 <= report.energy_savings_pct <= 100.0

    def test_timestamp_set(self, analyzer):
        report = analyzer.analyze(b"time check")
        assert report.timestamp is not None

    def test_compressible_text_positive_savings(self, analyzer):
        """Highly repetitive text should produce positive energy savings."""
        repetitive = b"The Committee " * 200
        report = analyzer.analyze(repetitive)
        assert report.energy_savings_pct > 0, (
            "Repetitive text should compress well and show positive energy savings"
        )

    def test_energy_consistency(self, analyzer):
        """energy_compressed + savings should roughly equal energy_uncompressed."""
        report = analyzer.analyze(b"consistency check data " * 50)
        reconstructed = report.energy_compressed / (
            1 - report.energy_savings_pct / 100
        ) if report.energy_savings_pct != 100 else report.energy_uncompressed
        assert abs(reconstructed - report.energy_uncompressed) < 1.0


# ---------------------------------------------------------------------------
# analyze_corpus
# ---------------------------------------------------------------------------


class TestAnalyzeCorpus:
    def test_corpus_length_matches_input(self, analyzer):
        samples = [s.encode("utf-8") for s in SAMPLE_INSTITUTIONAL_TEXT]
        reports = analyzer.analyze_corpus(samples)
        assert len(reports) == len(samples)

    def test_empty_corpus_returns_empty(self, analyzer):
        assert analyzer.analyze_corpus([]) == []

    def test_all_reports_are_efficiency_reports(self, analyzer, all_samples_bytes):
        for report in analyzer.analyze_corpus(all_samples_bytes):
            assert isinstance(report, EfficiencyReport)

    def test_corpus_order_preserved(self, analyzer):
        samples = [s.encode("utf-8") for s in SAMPLE_SENSOR_DATA]
        reports = analyzer.analyze_corpus(samples)
        for i, (report, sample) in enumerate(zip(reports, samples)):
            assert report.input_bytes == len(sample), (
                f"Report {i} has wrong input_bytes — order may not be preserved"
            )


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


class TestSummary:
    def test_summary_empty_returns_zeros(self, analyzer):
        s = analyzer.summary([])
        assert s["sample_count"] == 0
        assert s["avg_compression_ratio"] == 0.0
        assert s["avg_energy_savings_pct"] == 0.0

    def test_summary_keys_present(self, analyzer, all_samples_bytes):
        reports = analyzer.analyze_corpus(all_samples_bytes)
        s = analyzer.summary(reports)
        assert "sample_count" in s
        assert "avg_compression_ratio" in s
        assert "avg_symbol_reduction_pct" in s
        assert "avg_energy_savings_pct" in s
        assert "best_case_savings_pct" in s
        assert "worst_case_savings_pct" in s

    def test_summary_sample_count(self, analyzer, all_samples_bytes):
        reports = analyzer.analyze_corpus(all_samples_bytes)
        s = analyzer.summary(reports)
        assert s["sample_count"] == len(all_samples_bytes)

    def test_summary_best_gte_avg_gte_worst(self, analyzer, all_samples_bytes):
        reports = analyzer.analyze_corpus(all_samples_bytes)
        s = analyzer.summary(reports)
        assert s["best_case_savings_pct"] >= s["avg_energy_savings_pct"]
        assert s["avg_energy_savings_pct"] >= s["worst_case_savings_pct"]

    def test_summary_avg_compression_ratio_positive(
        self, analyzer, all_samples_bytes
    ):
        reports = analyzer.analyze_corpus(all_samples_bytes)
        s = analyzer.summary(reports)
        assert s["avg_compression_ratio"] > 0

    def test_single_report_summary(self, analyzer):
        report = analyzer.analyze(b"single sample test")
        s = analyzer.summary([report])
        assert s["sample_count"] == 1
        assert s["best_case_savings_pct"] == s["worst_case_savings_pct"]
        assert s["best_case_savings_pct"] == s["avg_energy_savings_pct"]
