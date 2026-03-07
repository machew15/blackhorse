"""Tests for blackhorse.modulation.governance — SIMULATION ONLY."""

import pytest

from blackhorse.crypto.signing import BHLSigner
from blackhorse.modulation.analyzer import EfficiencyAnalyzer
from blackhorse.modulation.governance import (
    DecisionAttestor,
    GovernedOutput,
    ModulationConstraints,
    ModulationPolicy,
    PolicyViolationError,
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
def attestor(signing_key):
    return DecisionAttestor(node_id="test-node", signing_key=signing_key)

@pytest.fixture
def constraints():
    return ModulationConstraints(
        education_mode=True,
        require_attestation=True,
    )

@pytest.fixture
def policy(constraints, attestor):
    return ModulationPolicy(constraints=constraints, attestor=attestor)

@pytest.fixture
def analyzer():
    return EfficiencyAnalyzer(scheme=ModulationScheme.QAM64)

@pytest.fixture
def small_data():
    return SAMPLE_INSTITUTIONAL_TEXT[0].encode("utf-8")

@pytest.fixture
def small_report(analyzer, small_data):
    return analyzer.analyze(small_data)


# ---------------------------------------------------------------------------
# ModulationConstraints defaults
# ---------------------------------------------------------------------------


class TestModulationConstraints:
    def test_default_values(self):
        c = ModulationConstraints()
        assert c.max_symbol_rate == 1_000_000
        assert c.max_payload_bytes == 65_536
        assert c.min_compression_ratio == 1.0
        assert set(c.allowed_schemes) == {"BPSK", "QPSK", "QAM16", "QAM64"}
        assert c.require_attestation is True
        assert c.education_mode is True

    def test_custom_values(self):
        c = ModulationConstraints(
            max_payload_bytes=1024,
            allowed_schemes=["BPSK"],
            education_mode=False,
        )
        assert c.max_payload_bytes == 1024
        assert c.allowed_schemes == ["BPSK"]
        assert c.education_mode is False


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


class TestValidate:
    def test_approve_valid_payload(self, policy, small_data):
        ok, reason = policy.validate(small_data, ModulationScheme.QAM64)
        assert ok is True
        assert reason == "APPROVED"

    def test_reject_oversized_payload(self):
        c = ModulationConstraints(max_payload_bytes=10)
        p = ModulationPolicy(constraints=c)
        data = b"x" * 100
        ok, reason = p.validate(data, ModulationScheme.BPSK)
        assert ok is False
        assert "PAYLOAD_TOO_LARGE" in reason

    def test_reject_disallowed_scheme(self):
        c = ModulationConstraints(allowed_schemes=["BPSK"])
        p = ModulationPolicy(constraints=c)
        ok, reason = p.validate(b"test", ModulationScheme.QAM64)
        assert ok is False
        assert "SCHEME_NOT_ALLOWED" in reason

    def test_reject_insufficient_compression(self):
        # min_compression_ratio = 100.0 is impossible to achieve.
        c = ModulationConstraints(min_compression_ratio=100.0)
        p = ModulationPolicy(constraints=c)
        ok, reason = p.validate(b"hello world", ModulationScheme.BPSK)
        assert ok is False
        assert "COMPRESSION_BELOW_MINIMUM" in reason

    def test_compression_ratio_1_no_compression_check(self, small_data):
        # Default min_compression_ratio=1.0 means no compression check.
        c = ModulationConstraints(min_compression_ratio=1.0)
        p = ModulationPolicy(constraints=c)
        ok, _ = p.validate(small_data, ModulationScheme.QAM64)
        assert ok is True

    @pytest.mark.parametrize("scheme", list(ModulationScheme))
    def test_all_four_schemes_approved_by_default(self, scheme):
        p = ModulationPolicy(constraints=ModulationConstraints())
        data = b"scheme test payload"
        ok, reason = p.validate(data, scheme)
        assert ok is True
        assert reason == "APPROVED"

    def test_empty_allowed_schemes_rejects_all(self):
        c = ModulationConstraints(allowed_schemes=[])
        p = ModulationPolicy(constraints=c)
        for scheme in ModulationScheme:
            ok, _ = p.validate(b"data", scheme)
            assert ok is False


# ---------------------------------------------------------------------------
# apply()
# ---------------------------------------------------------------------------


class TestApply:
    def test_apply_returns_governed_output(self, policy, small_data, small_report):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert isinstance(gov, GovernedOutput)

    def test_apply_policy_approved_true(self, policy, small_data, small_report):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.policy_approved is True

    def test_apply_raises_on_violation(self):
        c = ModulationConstraints(max_payload_bytes=1)
        p = ModulationPolicy(constraints=c)
        analyzer = EfficiencyAnalyzer(scheme=ModulationScheme.QAM64)
        data = b"too large for this policy"
        report = analyzer.analyze(data)
        with pytest.raises(PolicyViolationError):
            p.apply(data, ModulationScheme.QAM64, report)

    def test_education_note_present_when_mode_on(
        self, policy, small_data, small_report
    ):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.education_note is not None
        assert len(gov.education_note) > 0

    def test_education_note_absent_when_mode_off(
        self, small_data, small_report
    ):
        c = ModulationConstraints(education_mode=False, require_attestation=False)
        p = ModulationPolicy(constraints=c)
        gov = p.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.education_note is None

    def test_attestation_packet_present_when_attestor_provided(
        self, policy, small_data, small_report
    ):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.attestation_packet is not None
        assert len(gov.attestation_packet) > 0

    def test_attestation_packet_absent_without_attestor(
        self, small_data, small_report
    ):
        c = ModulationConstraints(require_attestation=True)
        p = ModulationPolicy(constraints=c, attestor=None)
        gov = p.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.attestation_packet is None

    def test_attestation_packet_verifiable(
        self, policy, small_data, small_report, signing_key
    ):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.attestation_packet is not None
        assert BHLSigner().verify(gov.attestation_packet, signing_key)

    def test_governed_output_report_matches(
        self, policy, small_data, small_report
    ):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.report is small_report

    def test_governed_output_has_timestamp(
        self, policy, small_data, small_report
    ):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.timestamp is not None


# ---------------------------------------------------------------------------
# DecisionAttestor
# ---------------------------------------------------------------------------


class TestDecisionAttestor:
    def test_generate_key_returns_32_bytes(self):
        key = DecisionAttestor.generate_key()
        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_attest_returns_bytes(self, attestor, small_report):
        result = attestor.attest(small_report, "APPROVED")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_verify_with_correct_key(self, signing_key, attestor, small_report):
        signed = attestor.attest(small_report, "APPROVED")
        assert DecisionAttestor.verify(signed, signing_key) is True

    def test_verify_fails_with_wrong_key(self, attestor, small_report):
        signed = attestor.attest(small_report, "APPROVED")
        wrong_key = BHLSigner.generate_key()
        assert DecisionAttestor.verify(signed, wrong_key) is False


# ---------------------------------------------------------------------------
# GovernedOutput media extension fields
# ---------------------------------------------------------------------------


class TestGovernedOutputMediaExtension:
    def test_default_media_attestation_none(self, policy, small_data, small_report):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.media_attestation is None

    def test_default_provenance_chain_empty(self, policy, small_data, small_report):
        gov = policy.apply(small_data, ModulationScheme.QAM64, small_report)
        assert gov.provenance_chain == []
