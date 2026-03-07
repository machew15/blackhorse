"""
Phase 4D — CRYSTALS-Dilithium (ML-DSA) Post-Quantum Digital Signatures.

Implements CRYSTALS-Dilithium (NIST FIPS 204) at the Dilithium3 / ML-DSA-65
parameter set, which provides NIST security level 3 (approximately 192-bit
classical equivalent security).

NIST standardised Dilithium as ML-DSA; ML-DSA-65 corresponds to Dilithium3.
This module uses the liboqs Python bindings.

Key and signature sizes (ML-DSA-65 / Dilithium3)
-------------------------------------------------
  Public key : 1952 bytes
  Secret key : 4032 bytes
  Signature  : 3309 bytes (fixed-size, deterministic)

Usage
-----
    signer = DilithiumSigner()

    pub, sk = signer.generate_keypair()
    signature = signer.sign(message, sk)
    ok = signer.verify(message, signature, pub)
"""

from __future__ import annotations

import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import oqs as _oqs


# ---------------------------------------------------------------------------
# Algorithm selection
# ---------------------------------------------------------------------------

_PREFERRED = "ML-DSA-65"
_LEGACY_NAME = "Dilithium3"

def _pick_algorithm() -> str:
    """Return the best available Dilithium/ML-DSA algorithm name."""
    enabled = _oqs.get_enabled_sig_mechanisms()
    for candidate in (_PREFERRED, _LEGACY_NAME, "ML-DSA-44", "Dilithium2"):
        if candidate in enabled:
            return candidate
    raise RuntimeError(
        "No Dilithium/ML-DSA algorithm available in the current liboqs build. "
        f"Enabled signatures: {enabled}"
    )


_ALGORITHM: str = _pick_algorithm()


# ---------------------------------------------------------------------------
# DilithiumSigner
# ---------------------------------------------------------------------------

class DilithiumSigner:
    """
    CRYSTALS-Dilithium (ML-DSA) post-quantum digital signature scheme.

    This is a drop-in post-quantum replacement for the HMAC-SHA256 signing
    used in the classical Blackhorse pipeline. Use it in hybrid mode via
    BlackhorseSession for a transition-period layered defence.

    Algorithm: ML-DSA-65 (NIST FIPS 204 / Dilithium3), security level 3.
    """

    ALGORITHM: str = _ALGORITHM
    ALGORITHM_FIPS: str = _PREFERRED

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """
        Generate an ML-DSA-65 key pair.

        Returns
        -------
        tuple[bytes, bytes]
            (public_key, secret_key) where public_key is 1952 bytes and
            secret_key is 4032 bytes (for ML-DSA-65).
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sig = _oqs.Signature(self.ALGORITHM)
        public_key = sig.generate_keypair()
        secret_key = sig.export_secret_key()
        sig.free()
        return public_key, secret_key

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        """
        Sign a message with the given secret key.

        Parameters
        ----------
        message    : Arbitrary bytes to sign.
        secret_key : ML-DSA-65 secret key (4032 bytes).

        Returns
        -------
        bytes
            The 3309-byte ML-DSA-65 signature.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sig = _oqs.Signature(self.ALGORITHM, secret_key=secret_key)
        signature = sig.sign(message)
        sig.free()
        return signature

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """
        Verify an ML-DSA-65 signature.

        Parameters
        ----------
        message    : The original message bytes.
        signature  : The signature bytes to verify (3309 bytes for ML-DSA-65).
        public_key : The signer's public key (1952 bytes).

        Returns
        -------
        bool
            True if the signature is valid, False otherwise.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sig = _oqs.Signature(self.ALGORITHM)
        try:
            return sig.verify(message, signature, public_key)
        except Exception:
            return False
        finally:
            sig.free()

    def details(self) -> dict:
        """
        Return algorithm parameter details from liboqs.

        Returns
        -------
        dict
            Keys include claimed_nist_level, length_public_key,
            length_secret_key, length_signature.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sig = _oqs.Signature(self.ALGORITHM)
        d = sig.details
        sig.free()
        return d
