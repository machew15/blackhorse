"""
Stage 6 — HMAC-SHA256 + BHL Integrity Signing.

A ``SignedPacket`` wraps arbitrary bytes with an HMAC-SHA256 authentication
tag.  The tag is computed over the packet contents so that any modification
to the data or the header is detected.

Wire format
-----------
  ┌────────────────────────────────────────────────────────────┐
  │ SIGNED PACKET HEADER (8 bytes)                             │
  │   Magic   : 4 bytes  b'BHLS'                              │
  │   Version : 1 byte   0x01                                 │
  │   Flags   : 1 byte   0x00 (reserved)                      │
  │   Length  : 2 bytes  uint16 BE — length of payload        │
  ├────────────────────────────────────────────────────────────┤
  │ PAYLOAD  (variable — the bytes being signed)               │
  ├────────────────────────────────────────────────────────────┤
  │ HMAC-SHA256 TAG  (32 bytes)                                │
  │   HMAC-SHA256(key, magic + version + flags + length +      │
  │               payload)                                     │
  └────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import hmac as _hmac
import hashlib
import os
import struct
from dataclasses import dataclass


SIGN_MAGIC: bytes = b"BHLS"
SIGN_VERSION: int = 0x01
SIGN_HEADER_SIZE: int = 8   # magic(4) + version(1) + flags(1) + length(2)
HMAC_SIZE: int = 32          # SHA-256 digest length

KEY_SIZE: int = 32           # recommended signing key length


class SigningError(Exception):
    """Raised when a signed packet is malformed or the HMAC fails."""


@dataclass
class SignedPacket:
    """
    A payload with an HMAC-SHA256 authentication tag.

    Attributes
    ----------
    payload : The authenticated bytes.
    tag     : 32-byte HMAC-SHA256 over the serialised header + payload.
    """

    payload: bytes
    tag: bytes

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialise to wire format."""
        header = (
            SIGN_MAGIC
            + bytes([SIGN_VERSION, 0x00])
            + struct.pack(">H", len(self.payload))
        )
        return header + self.payload + self.tag

    # ------------------------------------------------------------------
    # Deserialisation (no verification — call BHLSigner.verify)
    # ------------------------------------------------------------------

    @classmethod
    def from_bytes(cls, data: bytes) -> "SignedPacket":
        """
        Parse a serialised ``SignedPacket`` without verifying the HMAC.

        Use ``BHLSigner.verify_and_extract`` to both parse and authenticate.
        """
        if len(data) < SIGN_HEADER_SIZE + HMAC_SIZE:
            raise SigningError(f"Packet too short: {len(data)} bytes")
        magic = data[:4]
        if magic != SIGN_MAGIC:
            raise SigningError(f"Invalid BHLS magic: {magic!r}")
        version = data[4]
        if version != SIGN_VERSION:
            raise SigningError(f"Unsupported BHLS version: {version}")
        payload_len = struct.unpack_from(">H", data, 6)[0]
        expected = SIGN_HEADER_SIZE + payload_len + HMAC_SIZE
        if len(data) < expected:
            raise SigningError(
                f"Packet truncated: expected {expected} bytes, got {len(data)}"
            )
        payload = data[SIGN_HEADER_SIZE : SIGN_HEADER_SIZE + payload_len]
        tag = data[SIGN_HEADER_SIZE + payload_len : expected]
        return cls(payload=payload, tag=tag)


class BHLSigner:
    """
    Signs and verifies packets using HMAC-SHA256.

    This is Stage 6 of the Blackhorse protocol stack.  It wraps the output
    of Stage 5 (the encrypted, key-wrapped blob) with an integrity tag so
    that the recipient can detect tampering before attempting decryption.
    """

    # ------------------------------------------------------------------
    # Signing
    # ------------------------------------------------------------------

    def sign(self, payload: bytes, key: bytes) -> bytes:
        """
        Wrap *payload* in a ``SignedPacket`` and return the wire bytes.

        Parameters
        ----------
        payload : The bytes to authenticate.
        key     : HMAC signing key (any length; 32 bytes recommended).

        Returns
        -------
        bytes
            Serialised ``SignedPacket`` including the HMAC tag.
        """
        packet = SignedPacket(payload=payload, tag=b"\x00" * HMAC_SIZE)
        # Compute HMAC over the full wire representation *excluding* the tag.
        wire_without_tag = (
            SIGN_MAGIC
            + bytes([SIGN_VERSION, 0x00])
            + struct.pack(">H", len(payload))
            + payload
        )
        tag = _hmac.new(key, wire_without_tag, hashlib.sha256).digest()
        packet.tag = tag
        return packet.to_bytes()

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_and_extract(self, signed_bytes: bytes, key: bytes) -> bytes:
        """
        Verify the HMAC of *signed_bytes* and return the authenticated payload.

        Raises ``SigningError`` if the HMAC does not match.
        """
        packet = SignedPacket.from_bytes(signed_bytes)
        wire_without_tag = (
            SIGN_MAGIC
            + bytes([SIGN_VERSION, 0x00])
            + struct.pack(">H", len(packet.payload))
            + packet.payload
        )
        expected_tag = _hmac.new(key, wire_without_tag, hashlib.sha256).digest()
        if not _hmac.compare_digest(expected_tag, packet.tag):
            raise SigningError(
                "HMAC verification failed: packet has been tampered with or "
                "the signing key is incorrect"
            )
        return packet.payload

    def verify(self, signed_bytes: bytes, key: bytes) -> bool:
        """Return ``True`` if the HMAC is valid, ``False`` otherwise."""
        try:
            self.verify_and_extract(signed_bytes, key)
            return True
        except SigningError:
            return False

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_key() -> bytes:
        """Generate a cryptographically secure 256-bit signing key."""
        return os.urandom(KEY_SIZE)
