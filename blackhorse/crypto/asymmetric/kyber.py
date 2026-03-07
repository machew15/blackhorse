"""
Phase 4D — CRYSTALS-Kyber (ML-KEM) Post-Quantum Key Encapsulation.

Implements CRYSTALS-Kyber (NIST FIPS 203) at the Kyber-768 parameter set,
which provides NIST security level 3 (approximately 192-bit classical
equivalent security).

NIST standardised Kyber as ML-KEM-768; both names are used in the literature.
This module targets Kyber768 via the liboqs Python bindings.

Key sizes (Kyber768)
--------------------
  Public key  : 1184 bytes
  Secret key  : 2400 bytes
  Ciphertext  : 1088 bytes
  Shared secret: 32 bytes

Usage
-----
    kem = KyberKEM()

    # Recipient generates keypair.
    pub, sk = kem.generate_keypair()

    # Sender encapsulates: produces ciphertext + shared secret.
    ciphertext, shared_secret_sender = kem.encapsulate(pub)

    # Recipient decapsulates: recovers same shared secret.
    shared_secret_recipient = kem.decapsulate(sk, ciphertext)

    assert shared_secret_sender == shared_secret_recipient
"""

from __future__ import annotations

import warnings

# Suppress the liboqs version mismatch warning at import time.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import oqs as _oqs


# ---------------------------------------------------------------------------
# Algorithm selection
# ---------------------------------------------------------------------------

_PREFERRED = "Kyber768"
_FIPS_NAME = "ML-KEM-768"

def _pick_algorithm() -> str:
    """Return the best available Kyber/ML-KEM algorithm name."""
    enabled = _oqs.get_enabled_kem_mechanisms()
    for candidate in (_PREFERRED, _FIPS_NAME, "ML-KEM-512", "Kyber512"):
        if candidate in enabled:
            return candidate
    raise RuntimeError(
        "No Kyber/ML-KEM algorithm available in the current liboqs build. "
        f"Enabled KEMs: {enabled}"
    )


_ALGORITHM: str = _pick_algorithm()


# ---------------------------------------------------------------------------
# KyberKEM
# ---------------------------------------------------------------------------

class KyberKEM:
    """
    CRYSTALS-Kyber key encapsulation mechanism (KEM).

    This is a drop-in post-quantum replacement for the X25519 key exchange
    used in the classical Blackhorse pipeline. It can be used standalone
    or in hybrid mode alongside X25519 via BlackhorseSession.

    Algorithm: Kyber768 (NIST FIPS 203 / ML-KEM-768), security level 3.
    """

    ALGORITHM: str = _ALGORITHM
    ALGORITHM_FIPS: str = _FIPS_NAME

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """
        Generate a Kyber768 key pair.

        Returns
        -------
        tuple[bytes, bytes]
            (public_key, secret_key) where public_key is 1184 bytes and
            secret_key is 2400 bytes (for Kyber768).
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kem = _oqs.KeyEncapsulation(self.ALGORITHM)
        public_key = kem.generate_keypair()
        secret_key = kem.export_secret_key()
        kem.free()
        return public_key, secret_key

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        """
        Encapsulate a shared secret for the given public key.

        The encapsulated ciphertext is sent to the key-holder; the shared
        secret is used as a symmetric encryption key.

        Parameters
        ----------
        public_key : Recipient's Kyber768 public key (1184 bytes).

        Returns
        -------
        tuple[bytes, bytes]
            (ciphertext, shared_secret) where ciphertext is 1088 bytes and
            shared_secret is 32 bytes (for Kyber768).
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kem = _oqs.KeyEncapsulation(self.ALGORITHM)
        ciphertext, shared_secret = kem.encap_secret(public_key)
        kem.free()
        return ciphertext, shared_secret

    def decapsulate(self, secret_key: bytes, ciphertext: bytes) -> bytes:
        """
        Decapsulate a ciphertext to recover the shared secret.

        Parameters
        ----------
        secret_key : Recipient's Kyber768 secret key (2400 bytes).
        ciphertext : Ciphertext produced by encapsulate() (1088 bytes).

        Returns
        -------
        bytes
            The 32-byte shared secret matching that produced by the sender.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kem = _oqs.KeyEncapsulation(self.ALGORITHM, secret_key=secret_key)
        shared_secret = kem.decap_secret(ciphertext)
        kem.free()
        return shared_secret

    def details(self) -> dict:
        """
        Return algorithm parameter details from liboqs.

        Returns
        -------
        dict
            Keys include claimed_nist_level, length_public_key,
            length_secret_key, length_ciphertext, length_shared_secret.
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kem = _oqs.KeyEncapsulation(self.ALGORITHM)
        d = kem.details
        kem.free()
        return d
