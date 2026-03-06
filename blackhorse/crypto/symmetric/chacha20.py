"""
Stage 4 — ChaCha20 Symmetric Encryption.

Uses the RFC 8439 ChaCha20 stream cipher via the ``cryptography`` library.

Key    : 256 bits (32 bytes)
Nonce  : 96 bits  (12 bytes)
Counter: 32 bits  (starts at 0 by default)

The ``cryptography`` library's ``ChaCha20`` primitive expects a 16-byte
combined nonce formatted as:
    [counter: 4 bytes LE] + [nonce: 12 bytes]

``ChaCha20Cipher`` handles that packing transparently.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms


class ChaCha20Error(Exception):
    """Raised on ChaCha20 parameter or input errors."""


class ChaCha20Cipher:
    """
    Thin, stateless wrapper around RFC 8439 ChaCha20.

    ChaCha20 is a symmetric stream cipher: ``decrypt`` is identical to
    ``encrypt``.  The same ``(key, nonce, counter)`` triple must never be
    reused with different plaintext.
    """

    KEY_SIZE: int = 32     # 256 bits
    NONCE_SIZE: int = 12   # 96 bits (RFC 8439)

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def encrypt(
        self,
        key: bytes,
        nonce: bytes,
        plaintext: bytes,
        counter: int = 0,
    ) -> bytes:
        """
        Encrypt *plaintext* with ChaCha20.

        Parameters
        ----------
        key       : 32-byte symmetric key.
        nonce     : 12-byte nonce.  **Must be unique per (key, message).**
        plaintext : Arbitrary-length bytes to encrypt.
        counter   : Initial block counter (default 0).

        Returns
        -------
        bytes
            Ciphertext of the same length as *plaintext*.
        """
        self._validate_params(key, nonce)
        full_nonce = self._pack_nonce(nonce, counter)
        cipher = Cipher(algorithms.ChaCha20(key, full_nonce), mode=None)
        enc = cipher.encryptor()
        return enc.update(plaintext)

    def decrypt(
        self,
        key: bytes,
        nonce: bytes,
        ciphertext: bytes,
        counter: int = 0,
    ) -> bytes:
        """
        Decrypt *ciphertext* encrypted with the same ``(key, nonce, counter)``.

        Identical to ``encrypt`` — ChaCha20 is a symmetric XOR stream cipher.
        """
        return self.encrypt(key, nonce, ciphertext, counter)

    # ------------------------------------------------------------------
    # Key / nonce generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate_key() -> bytes:
        """Generate a cryptographically secure random 256-bit key."""
        return os.urandom(ChaCha20Cipher.KEY_SIZE)

    @staticmethod
    def generate_nonce() -> bytes:
        """Generate a cryptographically secure random 96-bit nonce."""
        return os.urandom(ChaCha20Cipher.NONCE_SIZE)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pack_nonce(nonce: bytes, counter: int) -> bytes:
        """Return the 16-byte nonce expected by the ``cryptography`` library."""
        import struct
        return struct.pack("<I", counter & 0xFFFF_FFFF) + nonce

    @staticmethod
    def _validate_params(key: bytes, nonce: bytes) -> None:
        if len(key) != ChaCha20Cipher.KEY_SIZE:
            raise ChaCha20Error(
                f"Key must be {ChaCha20Cipher.KEY_SIZE} bytes, got {len(key)}"
            )
        if len(nonce) != ChaCha20Cipher.NONCE_SIZE:
            raise ChaCha20Error(
                f"Nonce must be {ChaCha20Cipher.NONCE_SIZE} bytes, got {len(nonce)}"
            )
