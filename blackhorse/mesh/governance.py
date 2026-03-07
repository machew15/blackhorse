"""
Phase 3A — Contribution Receipt and Issuer.

Every successful relay generates a ContributionReceipt — a signed proof that
a specific node relayed a specific packet at a specific time. Receipts are
the trust currency of the Blackhorse Mesh: verifiable, unforgeable, tamper-evident.

No token. No blockchain. Cryptographic math only.
"""

from __future__ import annotations

import hashlib
import hmac as _hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..crypto.signing.hmac_bhl import BHLSigner, SigningError, KEY_SIZE
from ..language.encoder import BHLEncoder
from ..language.decoder import BHLDecoder
from ..compression.engine import compress, decompress


# ---------------------------------------------------------------------------
# ContributionReceipt
# ---------------------------------------------------------------------------

@dataclass
class ContributionReceipt:
    """
    A signed proof of relay participation.

    Attributes
    ----------
    receipt_id      : UUID uniquely identifying this receipt.
    relay_node_id   : node_id of the node that performed the relay.
    origin_node_id  : node_id of the message's originating node.
    message_id      : UUID of the relayed message.
    packet_hash     : SHA-256 hex of the relayed packet bytes.
    relay_timestamp : UTC datetime the relay occurred.
    bytes_relayed   : Number of bytes in the relayed packet.
    spatial_context : GeoJSON Point string or "unknown".
    signature       : HMAC-SHA256 over all above fields.
    """

    receipt_id: str
    relay_node_id: str
    origin_node_id: str
    message_id: str
    packet_hash: str
    relay_timestamp: datetime
    bytes_relayed: int
    spatial_context: str
    signature: bytes = field(default=b"")

    def _canonical_bytes(self) -> bytes:
        """
        Deterministic serialisation of all fields except signature.

        The canonical form is: receipt_id + relay_node_id + message_id +
        packet_hash + relay_timestamp ISO-8601, all joined with null bytes.
        """
        parts = [
            self.receipt_id,
            self.relay_node_id,
            self.message_id,
            self.packet_hash,
            self.relay_timestamp.isoformat(),
        ]
        return "\x00".join(parts).encode("utf-8")

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict."""
        return {
            "receipt_id": self.receipt_id,
            "relay_node_id": self.relay_node_id,
            "origin_node_id": self.origin_node_id,
            "message_id": self.message_id,
            "packet_hash": self.packet_hash,
            "relay_timestamp": self.relay_timestamp.isoformat(),
            "bytes_relayed": self.bytes_relayed,
            "spatial_context": self.spatial_context,
            "signature": self.signature.hex(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ContributionReceipt":
        """Reconstruct from a JSON-safe dict."""
        return cls(
            receipt_id=data["receipt_id"],
            relay_node_id=data["relay_node_id"],
            origin_node_id=data["origin_node_id"],
            message_id=data["message_id"],
            packet_hash=data["packet_hash"],
            relay_timestamp=datetime.fromisoformat(data["relay_timestamp"]),
            bytes_relayed=int(data["bytes_relayed"]),
            spatial_context=data.get("spatial_context", "unknown"),
            signature=bytes.fromhex(data["signature"]),
        )


# ---------------------------------------------------------------------------
# ContributionIssuer
# ---------------------------------------------------------------------------

class ContributionIssuer:
    """
    Issues and verifies ContributionReceipt objects.

    A ContributionIssuer is owned by a single relay node. Each receipt it
    issues is signed with the node's HMAC key, making it attributable and
    tamper-evident.

    Parameters
    ----------
    node_id     : This node's hex SHA-256 node_id.
    signing_key : 32-byte HMAC key.
    """

    def __init__(self, node_id: str, signing_key: bytes) -> None:
        self._node_id = node_id
        self._signing_key = signing_key

    def issue(
        self,
        relay_node_id: str,
        message_id: str,
        packet_bytes: bytes,
        relay_location: str = "unknown",
    ) -> ContributionReceipt:
        """
        Create and sign a ContributionReceipt for a completed relay.

        Parameters
        ----------
        relay_node_id  : node_id of the node that did the relaying.
        message_id     : UUID of the message that was relayed.
        packet_bytes   : The raw bytes that were relayed.
        relay_location : GeoJSON Point string or "unknown".

        Returns
        -------
        ContributionReceipt
            Signed receipt ready for storage or transmission.
        """
        packet_hash = hashlib.sha256(packet_bytes).hexdigest()
        receipt = ContributionReceipt(
            receipt_id=str(uuid.uuid4()),
            relay_node_id=relay_node_id,
            origin_node_id=self._node_id,
            message_id=message_id,
            packet_hash=packet_hash,
            relay_timestamp=datetime.now(timezone.utc),
            bytes_relayed=len(packet_bytes),
            spatial_context=relay_location,
        )
        receipt.signature = _hmac.new(
            self._signing_key,
            receipt._canonical_bytes(),
            __import__("hashlib").sha256,
        ).digest()
        return receipt

    def verify(self, receipt: ContributionReceipt, signing_key: bytes) -> bool:
        """
        Verify the HMAC signature on a ContributionReceipt.

        Parameters
        ----------
        receipt     : The receipt to verify.
        signing_key : The signing key of the issuing node.

        Returns
        -------
        bool
            True if the signature is valid, False otherwise.
        """
        if not receipt.signature:
            return False
        expected = _hmac.new(
            signing_key,
            receipt._canonical_bytes(),
            __import__("hashlib").sha256,
        ).digest()
        return _hmac.compare_digest(expected, receipt.signature)

    def serialize(self, receipt: ContributionReceipt) -> bytes:
        """
        Serialise a ContributionReceipt through the BHL pipeline.

        Pipeline: JSON → BHL encode → compress → HMAC sign.

        Parameters
        ----------
        receipt : The receipt to serialise.

        Returns
        -------
        bytes
            Signed, compressed, BHL-encoded packet bytes.
        """
        json_bytes = json.dumps(
            receipt.to_dict(), separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        bhl_bytes = BHLEncoder().encode_bytes(json_bytes)
        compressed = compress(bhl_bytes)
        return BHLSigner().sign(compressed, self._signing_key)

    def deserialize(
        self,
        packet_bytes: bytes,
        signing_key: bytes,
    ) -> ContributionReceipt:
        """
        Verify and deserialise a packed ContributionReceipt.

        Parameters
        ----------
        packet_bytes : Bytes produced by serialize().
        signing_key  : HMAC key used to verify the outer BHL signature.

        Returns
        -------
        ContributionReceipt

        Raises
        ------
        SigningError
            If HMAC verification of the outer packet fails.
        """
        compressed = BHLSigner().verify_and_extract(packet_bytes, signing_key)
        bhl_bytes = decompress(compressed)
        json_bytes = BHLDecoder().decode_bytes(bhl_bytes)
        return ContributionReceipt.from_dict(json.loads(json_bytes.decode("utf-8")))
