"""
Blackhorse Modulation Simulation — Standalone Demo
===================================================
SIMULATION ONLY — no RF transmission, no hardware, no spectrum use.

Run with:  python -m blackhorse.modulation.demo
"""

from __future__ import annotations

from blackhorse.crypto.signing import BHLSigner
from blackhorse.modulation.analyzer import EfficiencyAnalyzer
from blackhorse.modulation.governance import (
    DecisionAttestor,
    ModulationConstraints,
    ModulationPolicy,
)
from blackhorse.modulation.media import (
    InterruptHandler,
    MediaAttestor,
    MediaConstraints,
)
from blackhorse.modulation.media_analyzer import MediaEfficiencyAnalyzer
from blackhorse.modulation.runner import (
    SimulationRunner,
    print_report,
)
from blackhorse.modulation.samples import SAMPLE_INSTITUTIONAL_TEXT
from blackhorse.modulation.symbols import ModulationScheme


def main() -> None:
    # ---------------------------------------------------------------
    # 1. Build shared components
    # ---------------------------------------------------------------
    signing_key = BHLSigner.generate_key()
    attestor = DecisionAttestor(node_id="demo-node-01", signing_key=signing_key)

    constraints = ModulationConstraints(
        education_mode=True,
        require_attestation=True,
    )
    policy = ModulationPolicy(constraints=constraints, attestor=attestor)
    analyzer = EfficiencyAnalyzer(scheme=ModulationScheme.QAM64)
    runner = SimulationRunner(
        policy=policy, analyzer=analyzer, signing_key=signing_key
    )

    # ---------------------------------------------------------------
    # 2. Scheme comparison — first institutional sample
    # ---------------------------------------------------------------
    sample_text = SAMPLE_INSTITUTIONAL_TEXT[0]

    print("\n" + "═" * 79)
    print(" BLACKHORSE MODULATION SIMULATION DEMO".center(79))
    print(" SIMULATION ONLY — NOT REAL RF DATA".center(79))
    print("═" * 79)
    print("\nRunning scheme comparison on first institutional sample...\n")

    comparison = runner.run_comparison(sample_text)
    print_report(comparison)

    # ---------------------------------------------------------------
    # 3. Full corpus simulation — QAM64
    # ---------------------------------------------------------------
    print("\nRunning institutional corpus simulation (QAM64)...\n")

    corpus_result = runner.run_institutional_corpus(
        texts=SAMPLE_INSTITUTIONAL_TEXT,
        scheme=ModulationScheme.QAM64,
        corpus_name="institutional_corpus",
    )
    print_report(corpus_result)

    # ---------------------------------------------------------------
    # 4. Education note from first governed output
    # ---------------------------------------------------------------
    if corpus_result.governed_outputs:
        first = corpus_result.governed_outputs[0]
        if first.education_note:
            print("\n" + first.education_note + "\n")

    # ---------------------------------------------------------------
    # 5. Media simulation
    # ---------------------------------------------------------------
    print("\nRunning media corpus simulation...\n")

    media_key = BHLSigner.generate_key()
    interrupt_handler = InterruptHandler(
        signing_key=media_key, operator_id="demo-operator"
    )
    media_constraints = MediaConstraints(education_mode=True)
    media_attestor = MediaAttestor(
        node_id="demo-node-01",
        signing_key=media_key,
        interrupt_handler=interrupt_handler,
        constraints=media_constraints,
    )
    media_analyzer = MediaEfficiencyAnalyzer(
        scheme=ModulationScheme.QAM64,
        constraints=media_constraints,
        attestor=media_attestor,
    )
    media_policy = ModulationPolicy(
        constraints=constraints,
        attestor=attestor,
        media_constraints=media_constraints,
        media_attestor=media_attestor,
    )
    media_runner = SimulationRunner(
        policy=media_policy,
        analyzer=media_analyzer,
        signing_key=signing_key,
    )

    media_result = media_runner.run_media_simulation()
    print_report(media_result)

    # Governance notes for each synthetic media item.
    print("\n" + "─" * 79)
    print("  MEDIA GOVERNANCE NOTES")
    print("─" * 79)
    for report in media_result.reports:
        print(f"\n  [{report.media_type.upper()}]  {report.filename}")
        for line in report.governance_note.splitlines():
            print(f"    {line}")

    # ---------------------------------------------------------------
    # 6. Closing simulation note
    # ---------------------------------------------------------------
    # ---------------------------------------------------------------
    # 7. Attestation summary
    # ---------------------------------------------------------------
    print("─" * 79)
    print("  ALL OUTPUTS SIGNED VIA BLACKHORSE PROTOCOL")
    print("  Attestation: HMAC-SHA256 over report fields + governance decision")
    print("  Provenance:  SHA-256 content hash per media item (verifiable locally)")
    print("  Receipts:    Stored as signed BHL packet bytes — no network transfer")
    print("─" * 79)

    print("""
---
SIMULATION NOTE:
These results model the theoretical efficiency of applying BHL compression
before modulation symbol encoding. All numbers are relative simulation
units — not real watts, not real RF data, not real transmission.

This is a research instrument for understanding compression efficiency
in low-bandwidth environments. No spectrum was used. No signals were
transmitted. This is math, not radio.

SIMULATION — Nothing leaves the machine.
---
""")


if __name__ == "__main__":
    main()
