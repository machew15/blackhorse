"""Tests for blackhorse.modulation.runner — SIMULATION ONLY."""

import pytest

from blackhorse.crypto.signing import BHLSigner
from blackhorse.modulation.analyzer import EfficiencyAnalyzer
from blackhorse.modulation.governance import (
    GovernedOutput,
    ModulationConstraints,
    ModulationPolicy,
)
from blackhorse.modulation.runner import (
    ComparisonResult,
    MediaSimulationResult,
    SimulationResult,
    SimulationRunner,
    print_report,
)
from blackhorse.modulation.samples import SAMPLE_INSTITUTIONAL_TEXT
from blackhorse.modulation.symbols import ModulationScheme


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def signing_key():
    return BHLSigner.generate_key()

@pytest.fixture
def policy():
    return ModulationPolicy(constraints=ModulationConstraints())

@pytest.fixture
def analyzer():
    return EfficiencyAnalyzer(scheme=ModulationScheme.QAM64)

@pytest.fixture
def runner(policy, analyzer, signing_key):
    return SimulationRunner(
        policy=policy, analyzer=analyzer, signing_key=signing_key
    )

@pytest.fixture
def runner_no_key(policy, analyzer):
    return SimulationRunner(policy=policy, analyzer=analyzer)

@pytest.fixture
def sample_text():
    return SAMPLE_INSTITUTIONAL_TEXT[0]


# ---------------------------------------------------------------------------
# run_text_sample
# ---------------------------------------------------------------------------


class TestRunTextSample:
    def test_returns_governed_output(self, runner, sample_text):
        gov = runner.run_text_sample(sample_text, ModulationScheme.QAM64)
        assert isinstance(gov, GovernedOutput)

    def test_policy_approved(self, runner, sample_text):
        gov = runner.run_text_sample(sample_text, ModulationScheme.QAM64)
        assert gov.policy_approved is True

    def test_report_input_bytes_match(self, runner, sample_text):
        gov = runner.run_text_sample(sample_text, ModulationScheme.QAM64)
        assert gov.report.input_bytes == len(sample_text.encode("utf-8"))

    @pytest.mark.parametrize("scheme", list(ModulationScheme))
    def test_all_schemes_produce_output(self, runner, sample_text, scheme):
        gov = runner.run_text_sample(sample_text, scheme)
        assert isinstance(gov, GovernedOutput)

    def test_empty_string_handled(self, runner):
        gov = runner.run_text_sample("", ModulationScheme.BPSK)
        assert gov.report.input_bytes == 0


# ---------------------------------------------------------------------------
# run_comparison
# ---------------------------------------------------------------------------


class TestRunComparison:
    def test_returns_comparison_result(self, runner, sample_text):
        result = runner.run_comparison(sample_text)
        assert isinstance(result, ComparisonResult)

    def test_covers_all_four_schemes(self, runner, sample_text):
        result = runner.run_comparison(sample_text)
        assert set(result.results.keys()) == {"BPSK", "QPSK", "QAM16", "QAM64"}

    def test_most_efficient_scheme_is_valid(self, runner, sample_text):
        result = runner.run_comparison(sample_text)
        assert result.most_efficient_scheme in {"BPSK", "QPSK", "QAM16", "QAM64"}

    def test_input_text_preserved(self, runner, sample_text):
        result = runner.run_comparison(sample_text)
        assert result.input_text == sample_text

    def test_each_result_is_governed_output(self, runner, sample_text):
        result = runner.run_comparison(sample_text)
        for name, gov in result.results.items():
            assert isinstance(gov, GovernedOutput), (
                f"Expected GovernedOutput for scheme {name}"
            )

    def test_timestamp_set(self, runner, sample_text):
        result = runner.run_comparison(sample_text)
        assert result.timestamp is not None


# ---------------------------------------------------------------------------
# run_institutional_corpus
# ---------------------------------------------------------------------------


class TestRunInstitutionalCorpus:
    def test_returns_simulation_result(self, runner):
        result = runner.run_institutional_corpus(
            texts=SAMPLE_INSTITUTIONAL_TEXT,
            scheme=ModulationScheme.QAM64,
        )
        assert isinstance(result, SimulationResult)

    def test_sample_count_matches(self, runner):
        texts = SAMPLE_INSTITUTIONAL_TEXT[:3]
        result = runner.run_institutional_corpus(
            texts=texts, scheme=ModulationScheme.QAM64
        )
        assert result.sample_count == 3

    def test_governed_outputs_count(self, runner):
        texts = SAMPLE_INSTITUTIONAL_TEXT[:4]
        result = runner.run_institutional_corpus(
            texts=texts, scheme=ModulationScheme.QAM64
        )
        assert len(result.governed_outputs) == 4

    def test_empty_corpus_handled_gracefully(self, runner):
        result = runner.run_institutional_corpus(
            texts=[], scheme=ModulationScheme.QAM64
        )
        assert isinstance(result, SimulationResult)
        assert result.sample_count == 0
        assert result.governed_outputs == []
        assert result.summary["sample_count"] == 0

    def test_scheme_name_in_result(self, runner):
        result = runner.run_institutional_corpus(
            texts=SAMPLE_INSTITUTIONAL_TEXT[:2],
            scheme=ModulationScheme.BPSK,
        )
        assert result.scheme == "BPSK"

    def test_signed_report_present_with_key(self, runner):
        result = runner.run_institutional_corpus(
            texts=SAMPLE_INSTITUTIONAL_TEXT[:2],
            scheme=ModulationScheme.QAM64,
        )
        assert result.signed_report is not None
        assert isinstance(result.signed_report, bytes)

    def test_signed_report_absent_without_key(self, runner_no_key):
        result = runner_no_key.run_institutional_corpus(
            texts=SAMPLE_INSTITUTIONAL_TEXT[:2],
            scheme=ModulationScheme.QAM64,
        )
        assert result.signed_report is None

    def test_summary_has_required_keys(self, runner):
        result = runner.run_institutional_corpus(
            texts=SAMPLE_INSTITUTIONAL_TEXT,
            scheme=ModulationScheme.QAM64,
        )
        s = result.summary
        assert "sample_count" in s
        assert "avg_compression_ratio" in s
        assert "avg_energy_savings_pct" in s

    def test_corpus_name_preserved(self, runner):
        result = runner.run_institutional_corpus(
            texts=SAMPLE_INSTITUTIONAL_TEXT[:1],
            scheme=ModulationScheme.QAM64,
            corpus_name="fed_transcripts",
        )
        assert result.corpus_name == "fed_transcripts"


# ---------------------------------------------------------------------------
# print_report — smoke tests (should not raise)
# ---------------------------------------------------------------------------


class TestPrintReport:
    def test_print_simulation_result(self, runner, capsys):
        result = runner.run_institutional_corpus(
            texts=SAMPLE_INSTITUTIONAL_TEXT[:2],
            scheme=ModulationScheme.QAM64,
        )
        print_report(result)
        captured = capsys.readouterr()
        assert "SIMULATION" in captured.out
        assert "QAM64" in captured.out

    def test_print_comparison_result(self, runner, sample_text, capsys):
        result = runner.run_comparison(sample_text)
        print_report(result)
        captured = capsys.readouterr()
        assert "SIMULATION" in captured.out
        assert "BPSK" in captured.out
        assert "QAM64" in captured.out

    def test_print_unknown_type_does_not_raise(self, capsys):
        print_report(object())
        captured = capsys.readouterr()
        assert "Unknown result type" in captured.out
