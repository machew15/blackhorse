"""
SIMULATION ONLY — Mathematical symbol mapping. No RF transmission.

SymbolMapper models how bytes would map to OFDM-style modulation symbol
indices. All output is pure integer simulation — no waveforms, no spectrum,
no hardware. Energy estimates are relative simulation units only.
"""

from __future__ import annotations

import enum
import math


class ModulationScheme(enum.IntEnum):
    """Simulated modulation scheme — defines bits encoded per symbol.

    Higher schemes pack more bits per symbol, requiring fewer symbols to
    transmit the same data, but are more sensitive to noise (simulated only).
    """

    BPSK  = 1  # Binary Phase Shift Keying  — 1 bit  per symbol
    QPSK  = 2  # Quadrature PSK             — 2 bits per symbol
    QAM16 = 4  # 16-QAM                     — 4 bits per symbol
    QAM64 = 6  # 64-QAM                     — 6 bits per symbol


class SymbolMapper:
    """Maps bytes to modulation symbol indices — pure integer simulation.

    No RF waveform is generated. Symbol indices are integers representing
    which constellation point a chunk of bits maps to. This is a mathematical
    model for studying compression efficiency, not a transmission system.

    SIMULATION ONLY — output is relative efficiency data, not real RF metrics.
    """

    def __init__(self, scheme: ModulationScheme) -> None:
        self._scheme = scheme
        self._bps = int(scheme)              # bits per symbol
        self._symbols_possible = 1 << self._bps  # 2^bps constellation points

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bits_per_symbol(self) -> int:
        """Return the number of bits encoded per symbol under this scheme."""
        return self._bps

    def symbol_count(self, data: bytes) -> int:
        """Return number of symbols needed to transmit *data* under this scheme.

        Pads to a whole number of symbols (partial last symbol counts as one).
        """
        if not data:
            return 0
        total_bits = len(data) * 8
        return math.ceil(total_bits / self._bps)

    def encode(self, data: bytes) -> list[int]:
        """Map *data* bytes to a list of integer symbol indices.

        Packs bits MSB-first into groups of ``bits_per_symbol()`` bits.
        The last group is zero-padded if the total bit count is not a
        multiple of ``bits_per_symbol()``.

        Returns an empty list for empty input.
        """
        if not data:
            return []

        bps = self._bps

        # Unpack all bytes into individual bits, MSB first.
        bits: list[int] = []
        for byte in data:
            for shift in range(7, -1, -1):
                bits.append((byte >> shift) & 1)

        # Zero-pad to a multiple of bps.
        remainder = len(bits) % bps
        if remainder:
            bits.extend([0] * (bps - remainder))

        # Group into symbol indices.
        symbols: list[int] = []
        for i in range(0, len(bits), bps):
            val = 0
            for bit in bits[i : i + bps]:
                val = (val << 1) | bit
            symbols.append(val)

        return symbols

    def decode(self, symbols: list[int]) -> bytes:
        """Reconstruct bytes from symbol indices (inverse of ``encode``).

        Unpacks ``bits_per_symbol()`` bits per symbol, MSB-first, then
        assembles whole bytes. Any trailing padding bits from the last
        symbol are discarded.

        Returns empty bytes for an empty symbol list.
        """
        if not symbols:
            return b""

        bps = self._bps

        # Expand each symbol into its constituent bits, MSB first.
        bits: list[int] = []
        for sym in symbols:
            for shift in range(bps - 1, -1, -1):
                bits.append((sym >> shift) & 1)

        # Convert bits to bytes, discarding any trailing padding.
        num_bytes = len(bits) // 8
        result = bytearray(num_bytes)
        for i in range(num_bytes):
            val = 0
            for bit in bits[i * 8 : (i + 1) * 8]:
                val = (val << 1) | bit
            result[i] = val

        return bytes(result)

    def energy_estimate(
        self, data: bytes, power_per_symbol: float = 1.0
    ) -> float:
        """Return a simulated energy cost for transmitting *data*.

        Energy (simulation units) = symbol_count × power_per_symbol.

        Units are ARBITRARY SIMULATION UNITS — not real watts, not real
        joules. Use this value only for relative comparison between the
        compressed and uncompressed variants of the same payload.
        """
        return float(self.symbol_count(data)) * power_per_symbol
