"""
Stage 5 — Curve25519 Asymmetric Key Exchange.

Uses X25519 (ECDH over Curve25519) via the ``cryptography`` library to
perform a Diffie–Hellman key exchange.  The shared secret is passed through
HKDF-SHA256 before being used as a symmetric key.

Typical usage
-------------
    # Recipient generates a long-term keypair and publishes the public key.
    recipient_kp = Curve25519.generate()

    # Sender creates an ephemeral keypair for each message.
    sender_kp = Curve25519.generate()

    # Sender derives the shared key using the recipient's public key.
    shared = Curve25519.exchange(sender_kp, recipient_kp.public_key_bytes)

    # Recipient derives the same shared key using the sender's ephemeral pub.
    assert shared == Curve25519.exchange(recipient_kp, sender_kp.public_key_bytes)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

PUBLIC_KEY_SIZE: int = 32   # X25519 public keys are always 32 bytes
DERIVED_KEY_SIZE: int = 32  # 256-bit derived symmetric key


@dataclass
class KeyPair:
    """
    An X25519 key pair.

    Attributes
    ----------
    private_key      : ``X25519PrivateKey`` object (keep secret).
    public_key_bytes : 32-byte raw public key for sharing.
    """

    private_key: X25519PrivateKey
    public_key_bytes: bytes = field(init=False)

    def __post_init__(self) -> None:
        pub = self.private_key.public_key()
        self.public_key_bytes = pub.public_bytes(Encoding.Raw, PublicFormat.Raw)

    def private_key_bytes(self) -> bytes:
        """Return the raw 32-byte private key (handle with care)."""
        return self.private_key.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )


class Curve25519:
    """
    Namespace for X25519 ECDH operations and HKDF-based key derivation.
    """

    # ------------------------------------------------------------------
    # Key generation
    # ------------------------------------------------------------------

    @staticmethod
    def generate() -> KeyPair:
        """Generate a fresh X25519 key pair."""
        priv = X25519PrivateKey.generate()
        return KeyPair(private_key=priv)

    @staticmethod
    def from_private_bytes(raw: bytes) -> KeyPair:
        """Reconstruct a ``KeyPair`` from 32 raw private-key bytes."""
        if len(raw) != 32:
            raise ValueError(f"Private key must be 32 bytes, got {len(raw)}")
        priv = X25519PrivateKey.from_private_bytes(raw)
        return KeyPair(private_key=priv)

    # ------------------------------------------------------------------
    # ECDH + key derivation
    # ------------------------------------------------------------------

    @staticmethod
    def exchange(
        local_keypair: KeyPair,
        peer_public_bytes: bytes,
        info: bytes = b"blackhorse-v1",
        salt: bytes | None = None,
    ) -> bytes:
        """
        Perform X25519 ECDH and derive a 256-bit symmetric key via HKDF-SHA256.

        Parameters
        ----------
        local_keypair     : The local ``KeyPair`` (private key used for ECDH).
        peer_public_bytes : 32-byte raw X25519 public key of the peer.
        info              : HKDF info parameter (context binding).
        salt              : Optional HKDF salt; random bytes improve security.

        Returns
        -------
        bytes
            32-byte derived symmetric key suitable for ChaCha20.
        """
        if len(peer_public_bytes) != PUBLIC_KEY_SIZE:
            raise ValueError(
                f"Peer public key must be {PUBLIC_KEY_SIZE} bytes, "
                f"got {len(peer_public_bytes)}"
            )
        peer_pub = X25519PublicKey.from_public_bytes(peer_public_bytes)
        shared_secret = local_keypair.private_key.exchange(peer_pub)

        hkdf = HKDF(
            algorithm=SHA256(),
            length=DERIVED_KEY_SIZE,
            salt=salt,
            info=info,
        )
        return hkdf.derive(shared_secret)

    @staticmethod
    def generate_salt() -> bytes:
        """Generate a 32-byte cryptographically secure random salt."""
        return os.urandom(32)
