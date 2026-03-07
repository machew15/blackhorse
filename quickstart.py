"""
Blackhorse Mesh — Quickstart

Two simulated nodes perform a full offline-first handshake, message exchange,
and signed delivery receipt round-trip. No network calls. No hardware. Pure
in-memory simulation. Should complete in under 3 seconds.

Run with:
    python quickstart.py
"""

import sys
import os

# Ensure the workspace root is on the path when run directly.
sys.path.insert(0, os.path.dirname(__file__))

from blackhorse.interface.handshake import BlackhorseSession
from blackhorse.crypto.signing.hmac_bhl import BHLSigner
from blackhorse.mesh.queue import MessageQueue

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

SHARED_SIGNING_KEY = BHLSigner.generate_key()

node_a = BlackhorseSession(
    agent_info={"name": "node_a"},
    signing_key=SHARED_SIGNING_KEY,
)
node_b = BlackhorseSession(
    agent_info={"name": "node_b"},
    signing_key=SHARED_SIGNING_KEY,
)

queue_a = MessageQueue(":memory:")

MESSAGE = "Hello from node_a — mesh is live."

# ---------------------------------------------------------------------------
# Step 1: Pack
# ---------------------------------------------------------------------------

print("\n[PACK]     node_a → encrypting message...")
packet_bytes = node_a.pack(MESSAGE, node_b.public_key_bytes)
print(f"           packet size: {len(packet_bytes)} bytes")

# ---------------------------------------------------------------------------
# Step 2: Enqueue
# ---------------------------------------------------------------------------

message_id = queue_a.enqueue(
    packet_bytes=packet_bytes,
    recipient_pubkey=node_b.public_key_bytes,
    priority=2,
)
queue_a.mark_sent(message_id)
print(f"\n[SEND]     node_a → transmitting to node_b...")
print(f"           message_id: {message_id}")

# ---------------------------------------------------------------------------
# Step 3: Receive and unpack
# ---------------------------------------------------------------------------

print("\n[RECEIVE]  node_b → verifying packet...")
plaintext, metadata = node_b.unpack(packet_bytes, SHARED_SIGNING_KEY)
print(f"           decrypted: \"{plaintext}\"")
print(f"           sender:    {metadata['sender_pubkey'][:16]}...")

# ---------------------------------------------------------------------------
# Step 4: Generate receipt
# ---------------------------------------------------------------------------

print("\n[RECEIPT]  node_b → generating signed receipt...")
receipt_bytes = node_b.generate_receipt(message_id, SHARED_SIGNING_KEY)
print(f"           receipt size: {len(receipt_bytes)} bytes")

# ---------------------------------------------------------------------------
# Step 5: Verify receipt
# ---------------------------------------------------------------------------

print("\n[VERIFY]   node_a → receipt verified", end=" ")
receipt_payload = node_a.verify_receipt(receipt_bytes, SHARED_SIGNING_KEY)
print("✓")
print(f"           relay_node_id: {receipt_payload.relay_node_id}")
print(f"           timestamp:     {receipt_payload.timestamp.isoformat()}")

# ---------------------------------------------------------------------------
# Step 6: Acknowledge
# ---------------------------------------------------------------------------

queue_a.mark_acknowledged(message_id)
report = queue_a.status_report()

print(f"\n[STATUS]   message_id: {message_id}")
print(f"           → ACKNOWLEDGED")
print(f"           queue: {report}")

queue_a.close()

print("\nBlackhorse Mesh is live. You are the infrastructure.")
