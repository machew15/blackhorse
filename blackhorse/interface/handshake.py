"""
Stage 7 — Blackhorse Universal AI Handshake API.

``BlackhorseSession`` is the single entry point for the full protocol pipeline:

    Plaintext
       ↓  [BHL Encoding         — Stage 2]
    Encoded Stream
       ↓  [LZ77 Compression     — Stage 3]
    Compressed Bytes
       ↓  [ChaCha20 Encryption  — Stage 4]
    Encrypted Blob
       ↓  [Curve25519 Key Wrap  — Stage 5]
    Secured Package
       ↓  [HMAC-SHA256 Signing  — Stage 6]
    Final Blackhorse Packet (.bhp)

.bhp Wire Format
----------------
  ┌────────────────────────────────────────────────────────────────────┐
  │ BHP HEADER  (58 bytes)                                             │
  │   Magic            : 4 bytes   b'BHP\\x1A'                         │
  │   Version          : 1 byte    0x01                               │
  │   Flags            : 1 byte    0x00                               │
  │   Timestamp        : 8 bytes   Unix epoch seconds (uint64 BE)     │
  │   Sender Pub Key   : 32 bytes  Ephemeral X25519 public key        │
  │   Nonce            : 12 bytes  ChaCha20 nonce                     │
  ├────────────────────────────────────────────────────────────────────┤
  │ PAYLOAD LENGTH     : 4 bytes   uint32 BE                          │
  ├────────────────────────────────────────────────────────────────────┤
  │ PAYLOAD            : variable  HMAC-signed(encrypted(compressed(  │
  │                                BHL(plaintext))))                  │
  └────────────────────────────────────────────────────────────────────┘

Handshake Packet
----------------
A lightweight greeting/session-establishment packet (no encryption):

  ┌────────────────────────────────────────────────────────────────────┐
  │ HS HEADER  (8 bytes)                                               │
  │   Magic    : 4 bytes   b'BHHS'                                    │
  │   Version  : 1 byte    0x01                                       │
  │   Flags    : 1 byte    0x00                                       │
  │   Info Len : 2 bytes   uint16 BE                                  │
  ├────────────────────────────────────────────────────────────────────┤
  │ SESSION PUBLIC KEY  : 32 bytes  X25519 public key                 │
  ├────────────────────────────────────────────────────────────────────┤
  │ AGENT INFO  : <info_len> bytes  UTF-8 JSON describing the agent   │
  └────────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import json
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Any

from ..core.utils import pack_u32_be, unpack_u32_be
from ..language.encoder import BHLEncoder
from ..language.decoder import BHLDecoder
from ..compression.engine import compress, decompress
from ..crypto.symmetric.chacha20 import ChaCha20Cipher
from ..crypto.asymmetric.curve25519 import Curve25519, KeyPair
from ..crypto.signing.hmac_bhl import BHLSigner, SigningError

BHP_MAGIC: bytes = b"BHP\x1A"
BHP_VERSION: int = 0x01
BHP_HEADER_SIZE: int = 58   # 4+1+1+8+32+12

HS_MAGIC: bytes = b"BHHS"
HS_VERSION: int = 0x01
HS_HEADER_SIZE: int = 8    # 4+1+1+2
HS_PUBKEY_OFFSET: int = 8
HS_INFO_OFFSET: int = 40   # 8 + 32


class BHPError(Exception):
    """Raised when a .bhp packet is malformed or authentication fails."""


# ---------------------------------------------------------------------------
# BHP Packet data class
# ---------------------------------------------------------------------------

@dataclass
class BHPPacket:
    """
    Parsed representation of a .bhp packet.

    Attributes
    ----------
    timestamp          : Unix time the packet was created.
    sender_pubkey      : Ephemeral X25519 public key of the sender.
    nonce              : ChaCha20 nonce used for encryption.
    payload            : The signed+encrypted inner bytes.
    flags              : Flags byte.
    """

    timestamp: int
    sender_pubkey: bytes
    nonce: bytes
    payload: bytes
    flags: int = 0

    def to_bytes(self) -> bytes:
        """Serialise to wire format."""
        header = (
            BHP_MAGIC
            + bytes([BHP_VERSION, self.flags])
            + struct.pack(">Q", self.timestamp)
            + self.sender_pubkey
            + self.nonce
        )
        return header + pack_u32_be(len(self.payload)) + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "BHPPacket":
        """Parse and validate the BHP header; does not decrypt."""
        if len(data) < BHP_HEADER_SIZE + 4:
            raise BHPError(f"Packet too short: {len(data)}")
        magic = data[:4]
        if magic != BHP_MAGIC:
            raise BHPError(f"Invalid BHP magic: {magic!r}")
        version = data[4]
        if version != BHP_VERSION:
            raise BHPError(f"Unsupported BHP version: {version}")
        flags = data[5]
        timestamp = struct.unpack_from(">Q", data, 6)[0]
        sender_pubkey = data[14:46]
        nonce = data[46:58]
        payload_len = unpack_u32_be(data, 58)
        payload_end = 58 + 4 + payload_len
        if len(data) < payload_end:
            raise BHPError(
                f"Payload truncated: expected {payload_end} bytes, got {len(data)}"
            )
        payload = data[62 : payload_end]
        return cls(
            timestamp=timestamp,
            sender_pubkey=sender_pubkey,
            nonce=nonce,
            payload=payload,
            flags=flags,
        )


# ---------------------------------------------------------------------------
# BlackhorseSession
# ---------------------------------------------------------------------------

class BlackhorseSession:
    """
    Full-pipeline Blackhorse session for a single agent/participant.

    Each session owns an X25519 key pair used for Diffie–Hellman exchange.
    Call ``pack`` to encrypt and sign messages; ``unpack`` to verify and
    decrypt messages addressed to this session.

    Parameters
    ----------
    agent_info : Optional dictionary describing the agent (model, version, …).
                 Included unencrypted in handshake packets.
    signing_key : Optional 32-byte HMAC signing key.  If omitted, a fresh
                  random key is generated.  The sender and recipient must
                  share the same signing key for HMAC verification.
    """

    PROTOCOL_VERSION: str = "blackhorse-v1"

    def __init__(
        self,
        agent_info: dict[str, Any] | None = None,
        signing_key: bytes | None = None,
    ) -> None:
        self._keypair: KeyPair = Curve25519.generate()
        self._agent_info: dict[str, Any] = agent_info or {}
        self._signing_key: bytes = signing_key or BHLSigner.generate_key()

    # ------------------------------------------------------------------
    # Public key access
    # ------------------------------------------------------------------

    @property
    def public_key_bytes(self) -> bytes:
        """The 32-byte X25519 public key for this session."""
        return self._keypair.public_key_bytes

    @property
    def signing_key(self) -> bytes:
        """The 32-byte HMAC signing key for this session."""
        return self._signing_key

    # ------------------------------------------------------------------
    # Pack (encrypt + sign)
    # ------------------------------------------------------------------

    def pack(
        self,
        message: str | bytes,
        recipient_pubkey: bytes,
        signing_key: bytes | None = None,
    ) -> bytes:
        """
        Full-pipeline pack: BHL → compress → encrypt → sign → .bhp bytes.

        Parameters
        ----------
        message          : The plaintext string or bytes to send.
        recipient_pubkey : 32-byte X25519 public key of the recipient.
        signing_key      : Overrides the session signing key if provided.

        Returns
        -------
        bytes
            Serialised .bhp packet.
        """
        sig_key = signing_key if signing_key is not None else self._signing_key

        # --- Stage 2: BHL encode ---
        raw = message.encode("utf-8") if isinstance(message, str) else message
        bhl_bytes = BHLEncoder().encode_bytes(raw)

        # --- Stage 3: Compress ---
        compressed = compress(bhl_bytes)

        # --- Stage 4: Encrypt (ChaCha20) using ECDH-derived key ---
        ephemeral_kp = Curve25519.generate()
        derived_key = Curve25519.exchange(ephemeral_kp, recipient_pubkey)
        nonce = ChaCha20Cipher.generate_nonce()
        ciphertext = ChaCha20Cipher().encrypt(derived_key, nonce, compressed)

        # --- Stage 6: HMAC sign ---
        signed_payload = BHLSigner().sign(ciphertext, sig_key)

        # --- Assemble .bhp packet ---
        packet = BHPPacket(
            timestamp=int(time.time()),
            sender_pubkey=ephemeral_kp.public_key_bytes,
            nonce=nonce,
            payload=signed_payload,
        )
        return packet.to_bytes()

    # ------------------------------------------------------------------
    # Unpack (verify + decrypt)
    # ------------------------------------------------------------------

    def unpack(
        self,
        packet_bytes: bytes,
        signing_key: bytes | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Full-pipeline unpack: verify → decrypt → decompress → BHL decode.

        Parameters
        ----------
        packet_bytes : Bytes produced by ``BlackhorseSession.pack``.
        signing_key  : Overrides the session signing key if provided.

        Returns
        -------
        (message, metadata)
            *message*  — The original plaintext string.
            *metadata* — Dict with ``sender_pubkey``, ``timestamp``, etc.
        """
        raw_bytes, metadata = self.unpack_bytes(packet_bytes, signing_key)
        return raw_bytes.decode("utf-8"), metadata

    def unpack_bytes(
        self,
        packet_bytes: bytes,
        signing_key: bytes | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """
        Same as ``unpack`` but returns raw bytes instead of a string.
        """
        sig_key = signing_key if signing_key is not None else self._signing_key

        # --- Parse .bhp header ---
        packet = BHPPacket.from_bytes(packet_bytes)

        # --- Stage 6: Verify HMAC ---
        try:
            ciphertext = BHLSigner().verify_and_extract(packet.payload, sig_key)
        except SigningError as exc:
            raise BHPError(f"HMAC verification failed: {exc}") from exc

        # --- Stage 5: ECDH key derivation ---
        derived_key = Curve25519.exchange(self._keypair, packet.sender_pubkey)

        # --- Stage 4: Decrypt ---
        compressed = ChaCha20Cipher().decrypt(derived_key, packet.nonce, ciphertext)

        # --- Stage 3: Decompress ---
        bhl_bytes = decompress(compressed)

        # --- Stage 2: BHL decode ---
        raw = BHLDecoder().decode_bytes(bhl_bytes)

        metadata: dict[str, Any] = {
            "sender_pubkey": packet.sender_pubkey.hex(),
            "timestamp": packet.timestamp,
            "flags": packet.flags,
        }
        return raw, metadata

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

    def handshake(self) -> bytes:
        """
        Generate a session handshake packet.

        The handshake announces the session's X25519 public key and optional
        agent metadata.  It is **not encrypted** — it is intended to be sent
        first to establish a shared communication context.

        Returns
        -------
        bytes
            Serialised handshake packet.
        """
        info_json = json.dumps(
            {
                "protocol": self.PROTOCOL_VERSION,
                "timestamp": int(time.time()),
                **self._agent_info,
            },
            separators=(",", ":"),
        ).encode("utf-8")

        header = (
            HS_MAGIC
            + bytes([HS_VERSION, 0x00])
            + struct.pack(">H", len(info_json))
        )
        return header + self._keypair.public_key_bytes + info_json

    @classmethod
    def from_handshake(cls, handshake_bytes: bytes) -> "BlackhorseSession":
        """
        Parse a remote handshake packet and return a ``BlackhorseSession``
        pre-loaded with the remote agent's public key as ``agent_info``.

        Note: the returned session has a freshly generated key pair distinct
        from the remote peer's — it is ready to send a reply handshake or
        encrypt messages for that peer.
        """
        if len(handshake_bytes) < HS_INFO_OFFSET:
            raise BHPError(
                f"Handshake too short: {len(handshake_bytes)} bytes"
            )
        magic = handshake_bytes[:4]
        if magic != HS_MAGIC:
            raise BHPError(f"Invalid handshake magic: {magic!r}")
        version = handshake_bytes[4]
        if version != HS_VERSION:
            raise BHPError(f"Unsupported handshake version: {version}")
        info_len = struct.unpack_from(">H", handshake_bytes, 6)[0]
        pubkey = handshake_bytes[HS_PUBKEY_OFFSET : HS_PUBKEY_OFFSET + 32]
        info_raw = handshake_bytes[HS_INFO_OFFSET : HS_INFO_OFFSET + info_len]
        try:
            agent_info = json.loads(info_raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            agent_info = {}
        agent_info["_remote_pubkey"] = pubkey.hex()
        return cls(agent_info=agent_info)

    def __repr__(self) -> str:
        info_summary = ", ".join(
            f"{k}={v!r}"
            for k, v in list(self._agent_info.items())[:3]
        )
        return (
            f"BlackhorseSession("
            f"pubkey={self.public_key_bytes.hex()[:16]}…, "
            f"info={{{info_summary}}})"
        )
