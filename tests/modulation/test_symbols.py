"""Tests for blackhorse.modulation.symbols — SIMULATION ONLY."""

import pytest

from blackhorse.modulation.symbols import ModulationScheme, SymbolMapper


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_PAYLOADS = [
    b"Hello, world!",
    b"\x00\xff\xaa\x55",
    b"The Committee seeks to achieve maximum employment.",
    bytes(range(256)),
]


# ---------------------------------------------------------------------------
# ModulationScheme
# ---------------------------------------------------------------------------


class TestModulationScheme:
    def test_bps_values(self):
        assert ModulationScheme.BPSK == 1
        assert ModulationScheme.QPSK == 2
        assert ModulationScheme.QAM16 == 4
        assert ModulationScheme.QAM64 == 6

    def test_all_four_schemes_exist(self):
        names = {s.name for s in ModulationScheme}
        assert names == {"BPSK", "QPSK", "QAM16", "QAM64"}


# ---------------------------------------------------------------------------
# SymbolMapper — encode / decode round-trip
# ---------------------------------------------------------------------------


class TestSymbolMapper:
    @pytest.mark.parametrize("scheme", list(ModulationScheme))
    @pytest.mark.parametrize("payload", TEST_PAYLOADS)
    def test_roundtrip(self, scheme, payload):
        """encode → decode must recover original bytes exactly."""
        mapper = SymbolMapper(scheme)
        symbols = mapper.encode(payload)
        recovered = mapper.decode(symbols)
        assert recovered == payload, (
            f"Round-trip failed for scheme={scheme.name}, payload={payload!r}"
        )

    @pytest.mark.parametrize("scheme", list(ModulationScheme))
    def test_roundtrip_empty(self, scheme):
        mapper = SymbolMapper(scheme)
        assert mapper.encode(b"") == []
        assert mapper.decode([]) == b""

    @pytest.mark.parametrize("scheme", list(ModulationScheme))
    def test_roundtrip_single_byte(self, scheme):
        mapper = SymbolMapper(scheme)
        for byte_val in [0x00, 0xFF, 0xA5, 0x5A]:
            data = bytes([byte_val])
            assert mapper.decode(mapper.encode(data)) == data

    # ------------------------------------------------------------------
    # symbol_count math
    # ------------------------------------------------------------------

    def test_symbol_count_bpsk(self):
        # BPSK = 1 bit/symbol → 8 symbols per byte
        mapper = SymbolMapper(ModulationScheme.BPSK)
        assert mapper.symbol_count(b"\x00") == 8
        assert mapper.symbol_count(b"\x00\x00") == 16

    def test_symbol_count_qpsk(self):
        # QPSK = 2 bits/symbol → 4 symbols per byte
        mapper = SymbolMapper(ModulationScheme.QPSK)
        assert mapper.symbol_count(b"\x00") == 4
        assert mapper.symbol_count(b"\x00\x00") == 8

    def test_symbol_count_qam16(self):
        # QAM16 = 4 bits/symbol → 2 symbols per byte
        mapper = SymbolMapper(ModulationScheme.QAM16)
        assert mapper.symbol_count(b"\x00") == 2
        assert mapper.symbol_count(b"\x00\x00") == 4

    def test_symbol_count_qam64(self):
        # QAM64 = 6 bits/symbol → ceil(8/6) = 2 symbols per byte
        mapper = SymbolMapper(ModulationScheme.QAM64)
        assert mapper.symbol_count(b"\x00") == 2    # ceil(8/6)
        assert mapper.symbol_count(b"A" * 3) == 4   # ceil(24/6) = 4

    def test_symbol_count_empty(self):
        for scheme in ModulationScheme:
            assert SymbolMapper(scheme).symbol_count(b"") == 0

    def test_symbol_count_proportional_to_bits(self):
        """Larger data should require proportionally more symbols."""
        for scheme in ModulationScheme:
            mapper = SymbolMapper(scheme)
            small = b"A" * 10
            large = b"A" * 100
            assert mapper.symbol_count(large) > mapper.symbol_count(small)

    def test_higher_scheme_fewer_symbols(self):
        """Higher-order schemes pack more bits → fewer symbols for same data."""
        payload = b"hello simulation" * 10
        counts = [SymbolMapper(s).symbol_count(payload) for s in ModulationScheme]
        # BPSK > QPSK > QAM16 > QAM64 in symbol count
        assert counts[0] > counts[1] > counts[2] > counts[3]

    # ------------------------------------------------------------------
    # bits_per_symbol
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("scheme", list(ModulationScheme))
    def test_bits_per_symbol_matches_enum(self, scheme):
        mapper = SymbolMapper(scheme)
        assert mapper.bits_per_symbol() == int(scheme)

    # ------------------------------------------------------------------
    # energy_estimate
    # ------------------------------------------------------------------

    def test_energy_estimate_proportionality(self):
        """More data → more symbols → higher energy estimate."""
        mapper = SymbolMapper(ModulationScheme.QAM64)
        small = b"x" * 10
        large = b"x" * 100
        assert mapper.energy_estimate(large) > mapper.energy_estimate(small)

    def test_energy_estimate_power_scaling(self):
        """energy_estimate scales linearly with power_per_symbol."""
        mapper = SymbolMapper(ModulationScheme.QPSK)
        data = b"test"
        e1 = mapper.energy_estimate(data, power_per_symbol=1.0)
        e2 = mapper.energy_estimate(data, power_per_symbol=2.0)
        assert abs(e2 - 2 * e1) < 1e-9

    def test_energy_estimate_empty(self):
        for scheme in ModulationScheme:
            assert SymbolMapper(scheme).energy_estimate(b"") == 0.0

    def test_energy_estimate_equals_symbol_count_times_power(self):
        for scheme in ModulationScheme:
            mapper = SymbolMapper(scheme)
            data = b"simulation"
            power = 3.5
            expected = mapper.symbol_count(data) * power
            assert abs(mapper.energy_estimate(data, power) - expected) < 1e-9

    # ------------------------------------------------------------------
    # Symbol index bounds
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("scheme", list(ModulationScheme))
    def test_symbol_indices_in_range(self, scheme):
        """All symbol indices must be in [0, 2^bps - 1]."""
        mapper = SymbolMapper(scheme)
        max_val = (1 << int(scheme)) - 1
        for payload in TEST_PAYLOADS:
            for sym in mapper.encode(payload):
                assert 0 <= sym <= max_val, (
                    f"Symbol {sym} out of range for {scheme.name}"
                )
