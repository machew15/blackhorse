"""
Blackhorse Modulation Simulation Layer
=======================================
SIMULATION ONLY — no RF transmission, no radio hardware, no spectrum use.
All modulation is mathematical simulation in software only.

This module models:
- OFDM-style symbol mapping (integer indices, not waveforms)
- BHL compression efficiency analysis for bandwidth research
- Parametric governance constraints baked into the signal model
- Signed simulation outputs via Blackhorse Protocol attestation
- Media content provenance and governance

Output values are relative simulation units — NOT real watts, NOT real RF data,
NOT real spectrum measurements. This is a research and analysis instrument.
"""

from blackhorse.modulation.symbols import ModulationScheme, SymbolMapper
from blackhorse.modulation.analyzer import EfficiencyAnalyzer, EfficiencyReport
from blackhorse.modulation.governance import (
    ModulationConstraints,
    ModulationPolicy,
    GovernedOutput,
    PolicyViolationError,
    DecisionAttestor,
)
from blackhorse.modulation.runner import (
    SimulationRunner,
    SimulationResult,
    ComparisonResult,
    MediaSimulationResult,
    print_report,
)

__all__ = [
    "ModulationScheme",
    "SymbolMapper",
    "EfficiencyAnalyzer",
    "EfficiencyReport",
    "ModulationConstraints",
    "ModulationPolicy",
    "GovernedOutput",
    "PolicyViolationError",
    "DecisionAttestor",
    "SimulationRunner",
    "SimulationResult",
    "ComparisonResult",
    "MediaSimulationResult",
    "print_report",
]
