"""Tests for blackhorse.modulation.media and media_analyzer — SIMULATION ONLY."""

import pytest

from blackhorse.crypto.signing import BHLSigner
from blackhorse.modulation.media import (
    InterruptCommand,
    InterruptHandler,
    MediaAttestation,
    MediaAttestor,
    MediaConstraints,
    MediaType,
)
from blackhorse.modulation.media_analyzer import (
    MediaEfficiencyAnalyzer,
    MediaEfficiencyReport,
)
from blackhorse.modulation.governance import (
    ModulationConstraints,
    ModulationPolicy,
)
from blackhorse.modulation.runner import MediaSimulationResult, SimulationRunner
from blackhorse.modulation.samples import SAMPLE_INSTITUTIONAL_TEXT
from blackhorse.modulation.symbols import ModulationScheme


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def signing_key():
    return BHLSigner.generate_key()

@pytest.fixture
def interrupt_handler(signing_key):
    return InterruptHandler(signing_key=signing_key, operator_id="test-operator")

@pytest.fixture
def constraints():
    return MediaConstraints()

@pytest.fixture
def attestor(signing_key, interrupt_handler, constraints):
    return MediaAttestor(
        node_id="test-node",
        signing_key=signing_key,
        interrupt_handler=interrupt_handler,
        constraints=constraints,
    )

@pytest.fixture
def text_data():
    return SAMPLE_INSTITUTIONAL_TEXT[0].encode("utf-8")

@pytest.fixture
def png_data():
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 1000

@pytest.fixture
def mp3_data():
    return b"ID3" + b"\x00" * 2000

@pytest.fixture
def mp4_data():
    return b"\x00\x00\x00\x18ftyp" + b"\x00" * 5000

@pytest.fixture
def pdf_data():
    return b"%PDF-1.7\n" + b"(Simulation document content)\n" * 100

@pytest.fixture
def jpeg_data():
    return b"\xff\xd8\xff\xe0" + b"\x00" * 500

@pytest.fixture
def analyzer(attestor, constraints):
    return MediaEfficiencyAnalyzer(
        scheme=ModulationScheme.QAM64,
        constraints=constraints,
        attestor=attestor,
    )


# ---------------------------------------------------------------------------
# MediaType enum
# ---------------------------------------------------------------------------


class TestMediaType:
    def test_all_types_exist(self):
        values = {t.value for t in MediaType}
        assert "text" in values
        assert "image" in values
        assert "audio" in values
        assert "video" in values
        assert "document" in values
        assert "unknown" in values


# ---------------------------------------------------------------------------
# MediaAttestor.detect_type — magic bytes and extensions
# ---------------------------------------------------------------------------


class TestDetectType:
    def test_detect_jpeg_magic(self, attestor):
        data = b"\xff\xd8\xff" + b"\x00" * 100
        assert attestor.detect_type("photo.jpg", data) == MediaType.IMAGE

    def test_detect_png_magic(self, attestor, png_data):
        assert attestor.detect_type("image.png", png_data) == MediaType.IMAGE

    def test_detect_gif_magic(self, attestor):
        data = b"GIF8" + b"\x00" * 100
        assert attestor.detect_type("anim.gif", data) == MediaType.IMAGE

    def test_detect_mp3_id3(self, attestor, mp3_data):
        assert attestor.detect_type("track.mp3", mp3_data) == MediaType.AUDIO

    def test_detect_mp3_raw_frame(self, attestor):
        data = b"\xff\xfb" + b"\x00" * 500
        assert attestor.detect_type("track.mp3", data) == MediaType.AUDIO

    def test_detect_mp4_ftyp(self, attestor, mp4_data):
        assert attestor.detect_type("clip.mp4", mp4_data) == MediaType.VIDEO

    def test_detect_pdf_magic(self, attestor, pdf_data):
        assert attestor.detect_type("doc.pdf", pdf_data) == MediaType.DOCUMENT

    def test_detect_text_utf8(self, attestor, text_data):
        result = attestor.detect_type("notes.txt", text_data)
        assert result == MediaType.TEXT

    def test_detect_unknown_binary(self, attestor):
        # Non-UTF-8 binary that matches no magic.
        data = bytes(range(256)) * 4
        result = attestor.detect_type("blob.bin", data)
        assert result == MediaType.UNKNOWN

    def test_extension_detection_jpg(self, attestor, text_data):
        # Extension should win even if magic bytes match nothing.
        result = attestor.detect_type("photo.jpg", b"\x00" * 10)
        assert result == MediaType.IMAGE

    def test_extension_detection_mp4(self, attestor):
        result = attestor.detect_type("video.mp4", b"\x00" * 10)
        assert result == MediaType.VIDEO

    def test_extension_detection_pdf(self, attestor):
        result = attestor.detect_type("report.pdf", b"random bytes")
        assert result == MediaType.DOCUMENT


# ---------------------------------------------------------------------------
# MediaAttestor.attest
# ---------------------------------------------------------------------------


class TestAttest:
    def test_returns_media_attestation(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        assert isinstance(att, MediaAttestation)

    def test_content_hash_is_sha256_hex(self, attestor, signing_key, text_data):
        import hashlib
        att = attestor.attest(text_data, "sample.txt", signing_key)
        expected = hashlib.sha256(text_data).hexdigest()
        assert att.content_hash == expected

    def test_compressed_hash_set(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        assert len(att.compressed_hash) == 64  # SHA-256 hex

    def test_size_bytes_correct(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        assert att.size_bytes == len(text_data)

    def test_compression_ratio_positive(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        assert att.compression_ratio > 0

    def test_attested_by_node_id(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        assert att.attested_by == "test-node"

    def test_filename_stored(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "my_document.txt", signing_key)
        assert att.filename == "my_document.txt"

    def test_attestation_id_is_uuid(self, attestor, signing_key, text_data):
        import uuid
        att = attestor.attest(text_data, "sample.txt", signing_key)
        # Should not raise.
        uuid.UUID(att.attestation_id)

    def test_signature_is_bytes(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        assert isinstance(att.signature, bytes)
        assert len(att.signature) == 32  # HMAC-SHA256

    def test_video_human_approved_false(
        self, attestor, signing_key, mp4_data, capsys
    ):
        att = attestor.attest(mp4_data, "clip.mp4", signing_key)
        assert att.human_approved is False

    def test_non_video_human_approved_false_by_default(
        self, attestor, signing_key, png_data
    ):
        att = attestor.attest(png_data, "photo.png", signing_key)
        assert att.human_approved is False  # default — not yet approved

    def test_video_logs_notice(self, attestor, signing_key, mp4_data, capsys):
        attestor.attest(mp4_data, "clip.mp4", signing_key)
        captured = capsys.readouterr()
        assert "VIDEO" in captured.out
        assert "human_approved=False" in captured.out


# ---------------------------------------------------------------------------
# MediaAttestor.verify
# ---------------------------------------------------------------------------


class TestVerify:
    def test_verify_returns_true_on_unmodified_data(
        self, attestor, signing_key, text_data
    ):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        assert attestor.verify(att, text_data, signing_key) is True

    def test_verify_returns_false_on_tampered_data(
        self, attestor, signing_key, text_data
    ):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        tampered = text_data + b"\x00"
        assert attestor.verify(att, tampered, signing_key) is False

    def test_verify_returns_false_on_wrong_key(
        self, attestor, signing_key, text_data
    ):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        wrong_key = BHLSigner.generate_key()
        assert attestor.verify(att, text_data, wrong_key) is False

    def test_verify_returns_false_on_modified_hash(
        self, attestor, signing_key, text_data
    ):
        att = attestor.attest(text_data, "sample.txt", signing_key)
        att.content_hash = "a" * 64  # corrupt the stored hash
        assert attestor.verify(att, text_data, signing_key) is False


# ---------------------------------------------------------------------------
# MediaAttestor.approve
# ---------------------------------------------------------------------------


class TestApprove:
    def test_approve_sets_human_approved_true(
        self, attestor, signing_key, mp4_data
    ):
        att = attestor.attest(mp4_data, "clip.mp4", signing_key)
        assert att.human_approved is False
        attestor.approve(att, signing_key)
        assert att.human_approved is True

    def test_approve_attaches_receipt(
        self, attestor, signing_key, mp4_data
    ):
        att = attestor.attest(mp4_data, "clip.mp4", signing_key)
        attestor.approve(att, signing_key)
        assert att.approval_receipt is not None
        assert isinstance(att.approval_receipt, bytes)

    def test_approve_without_interrupt_handler(
        self, signing_key, mp4_data, constraints
    ):
        """approve() works even without an InterruptHandler configured."""
        att_no_handler = MediaAttestor(
            node_id="solo-node",
            signing_key=signing_key,
            constraints=constraints,
        )
        att = att_no_handler.attest(mp4_data, "clip.mp4", signing_key)
        att_no_handler.approve(att, signing_key)
        assert att.human_approved is True
        assert att.approval_receipt is not None

    def test_approve_returns_attestation(
        self, attestor, signing_key, mp4_data
    ):
        att = attestor.attest(mp4_data, "clip.mp4", signing_key)
        returned = attestor.approve(att, signing_key)
        assert returned is att


# ---------------------------------------------------------------------------
# MediaAttestor.serialize
# ---------------------------------------------------------------------------


class TestSerialize:
    def test_serialize_returns_bytes(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "doc.txt", signing_key)
        result = attestor.serialize(att)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_serialize_verifiable(self, attestor, signing_key, text_data):
        att = attestor.attest(text_data, "doc.txt", signing_key)
        serialized = attestor.serialize(att)
        assert BHLSigner().verify(serialized, signing_key)


# ---------------------------------------------------------------------------
# ModulationPolicy.validate_media
# ---------------------------------------------------------------------------


class TestValidateMedia:
    def test_no_media_policy_approves_all(self):
        p = ModulationPolicy(constraints=ModulationConstraints())
        ok, reason = p.validate_media(b"data", "file.txt", MediaType.TEXT)
        assert ok is True
        assert reason == "NO_MEDIA_POLICY"

    def test_video_always_rejected(self, attestor, constraints):
        p = ModulationPolicy(
            constraints=ModulationConstraints(),
            media_constraints=constraints,
            media_attestor=attestor,
        )
        ok, reason = p.validate_media(b"x" * 100, "clip.mp4", MediaType.VIDEO)
        assert ok is False
        assert "VIDEO_REQUIRES_HUMAN_APPROVAL" in reason

    def test_disallowed_type_rejected(self):
        mc = MediaConstraints(allowed_media_types=["text"])
        p = ModulationPolicy(
            constraints=ModulationConstraints(),
            media_constraints=mc,
        )
        ok, reason = p.validate_media(b"x" * 100, "photo.png", MediaType.IMAGE)
        assert ok is False
        assert "MEDIA_TYPE_NOT_ALLOWED" in reason

    def test_oversized_image_rejected(self):
        mc = MediaConstraints(max_image_bytes=100)
        p = ModulationPolicy(
            constraints=ModulationConstraints(),
            media_constraints=mc,
        )
        ok, reason = p.validate_media(b"x" * 200, "big.png", MediaType.IMAGE)
        assert ok is False
        assert "MEDIA_TOO_LARGE" in reason

    def test_text_approved(self, attestor, constraints):
        p = ModulationPolicy(
            constraints=ModulationConstraints(),
            media_constraints=constraints,
            media_attestor=attestor,
        )
        ok, reason = p.validate_media(b"Hello world", "doc.txt", MediaType.TEXT)
        assert ok is True
        assert reason == "APPROVED"


# ---------------------------------------------------------------------------
# MediaEfficiencyAnalyzer.simulate_media_corpus
# ---------------------------------------------------------------------------


class TestSimulateMediaCorpus:
    def test_returns_list(self, analyzer):
        reports = analyzer.simulate_media_corpus()
        assert isinstance(reports, list)

    def test_one_report_per_synthetic_type(self, analyzer):
        reports = analyzer.simulate_media_corpus()
        # We generate text, image, audio, video, document = 5 types.
        assert len(reports) == 5

    def test_all_reports_are_media_efficiency_reports(self, analyzer):
        for report in analyzer.simulate_media_corpus():
            assert isinstance(report, MediaEfficiencyReport)

    def test_governance_note_present_and_non_empty(self, analyzer):
        for report in analyzer.simulate_media_corpus():
            assert report.governance_note, (
                f"governance_note is empty for {report.media_type}"
            )

    def test_video_report_blocked(self, analyzer):
        reports = analyzer.simulate_media_corpus()
        video_reports = [r for r in reports if r.media_type == "video"]
        assert len(video_reports) == 1
        assert "VIDEO_REQUIRES_HUMAN_APPROVAL" in video_reports[0].governance_note

    def test_content_hash_set_for_all(self, analyzer):
        for report in analyzer.simulate_media_corpus():
            assert report.content_hash, (
                f"content_hash missing for {report.media_type}"
            )

    def test_provenance_verified_for_non_video(self, analyzer):
        reports = analyzer.simulate_media_corpus()
        non_video = [r for r in reports if r.media_type != "video"]
        for report in non_video:
            assert report.provenance_verified is True, (
                f"provenance_verified=False for {report.media_type}"
            )


# ---------------------------------------------------------------------------
# SimulationRunner.run_media_simulation (integration)
# ---------------------------------------------------------------------------


class TestRunMediaSimulation:
    @pytest.fixture
    def media_runner(self, attestor, constraints, signing_key):
        from blackhorse.modulation.media_analyzer import MediaEfficiencyAnalyzer
        media_analyzer = MediaEfficiencyAnalyzer(
            scheme=ModulationScheme.QAM64,
            constraints=constraints,
            attestor=attestor,
        )
        policy = ModulationPolicy(
            constraints=ModulationConstraints(),
            media_constraints=constraints,
            media_attestor=attestor,
        )
        return SimulationRunner(
            policy=policy,
            analyzer=media_analyzer,
            signing_key=signing_key,
        )

    def test_returns_media_simulation_result(self, media_runner):
        result = media_runner.run_media_simulation()
        assert isinstance(result, MediaSimulationResult)

    def test_video_blocked_count_positive(self, media_runner):
        result = media_runner.run_media_simulation()
        assert result.video_blocked_count >= 1

    def test_reports_non_empty(self, media_runner):
        result = media_runner.run_media_simulation()
        assert len(result.reports) > 0

    def test_signed_result_present(self, media_runner):
        result = media_runner.run_media_simulation()
        assert result.signed_result is not None

    def test_counts_sum_correctly(self, media_runner):
        result = media_runner.run_media_simulation()
        assert result.approved_count + result.rejected_count == len(result.reports)

    def test_summary_has_sample_count(self, media_runner):
        result = media_runner.run_media_simulation()
        assert "sample_count" in result.summary
        assert result.summary["sample_count"] == len(result.reports)
