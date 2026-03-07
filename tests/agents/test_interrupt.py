"""
Tests for blackhorse.agents.interrupt — InterruptHandler.

Covers:
- issue() creates a signed InterruptCommand
- verify() returns True for correctly signed command
- verify() returns False for tampered command
- verify() returns False for unsigned command (empty signature)
- verify() returns False for wrong signing key
- Invalid command type raises ValueError
- Long reason is truncated to 200 chars
- serialize / deserialize round-trip
- generate_receipt() returns bytes containing agent_id and status
- generate_receipt() is signed by agent key (different from operator key)
"""

import hashlib
import json

import pytest

from blackhorse.agents.interrupt import InterruptHandler, InterruptCommand, VALID_COMMANDS


OPERATOR_KEY = b"\x11" * 32
AGENT_KEY = b"\x22" * 32
ISSUER_ID = "operator-node-abc"
AGENT_ID = "agent-xyz-789"


@pytest.fixture
def handler():
    return InterruptHandler()


def test_issue_returns_interrupt_command(handler):
    cmd = handler.issue(AGENT_ID, "PAUSE", "routine check", ISSUER_ID, OPERATOR_KEY)
    assert isinstance(cmd, InterruptCommand)
    assert cmd.command == "PAUSE"
    assert cmd.issuer_id == ISSUER_ID
    assert cmd.target_agent_id == AGENT_ID


def test_issue_all_valid_commands(handler):
    for cmd_type in VALID_COMMANDS:
        cmd = handler.issue(AGENT_ID, cmd_type, "reason", ISSUER_ID, OPERATOR_KEY)
        assert cmd.command == cmd_type


def test_issue_invalid_command_raises(handler):
    with pytest.raises(ValueError):
        handler.issue(AGENT_ID, "EXPLODE", "reason", ISSUER_ID, OPERATOR_KEY)


def test_issue_signature_non_empty(handler):
    cmd = handler.issue(AGENT_ID, "STOP", "emergency stop", ISSUER_ID, OPERATOR_KEY)
    assert len(cmd.signature) == 32


def test_verify_returns_true_for_valid_command(handler):
    cmd = handler.issue(AGENT_ID, "PAUSE", "reason", ISSUER_ID, OPERATOR_KEY)
    assert handler.verify(cmd, OPERATOR_KEY)


def test_verify_returns_false_for_tampered_command(handler):
    cmd = handler.issue(AGENT_ID, "PAUSE", "reason", ISSUER_ID, OPERATOR_KEY)
    cmd.reason = "tampered reason"
    assert not handler.verify(cmd, OPERATOR_KEY)


def test_verify_returns_false_for_wrong_key(handler):
    cmd = handler.issue(AGENT_ID, "PAUSE", "reason", ISSUER_ID, OPERATOR_KEY)
    wrong_key = b"\x33" * 32
    assert not handler.verify(cmd, wrong_key)


def test_verify_returns_false_for_empty_signature(handler):
    cmd = handler.issue(AGENT_ID, "PAUSE", "reason", ISSUER_ID, OPERATOR_KEY)
    cmd.signature = b""
    assert not handler.verify(cmd, OPERATOR_KEY)


def test_reason_truncated_at_200_chars(handler):
    long_reason = "y" * 300
    cmd = handler.issue(AGENT_ID, "STOP", long_reason, ISSUER_ID, OPERATOR_KEY)
    assert len(cmd.reason) == 200


def test_command_id_unique_per_issue(handler):
    c1 = handler.issue(AGENT_ID, "PAUSE", "r", ISSUER_ID, OPERATOR_KEY)
    c2 = handler.issue(AGENT_ID, "PAUSE", "r", ISSUER_ID, OPERATOR_KEY)
    assert c1.command_id != c2.command_id


def test_serialize_deserialize_round_trip(handler):
    cmd = handler.issue(AGENT_ID, "REDIRECT", "rerouting", ISSUER_ID, OPERATOR_KEY)
    data = handler.serialize(cmd)
    restored = InterruptHandler.deserialize(data)
    assert restored.command_id == cmd.command_id
    assert restored.command == cmd.command
    assert restored.signature == cmd.signature
    assert handler.verify(restored, OPERATOR_KEY)


def test_generate_receipt_returns_bytes(handler):
    cmd = handler.issue(AGENT_ID, "PAUSE", "reason", ISSUER_ID, OPERATOR_KEY)
    receipt = handler.generate_receipt(cmd, AGENT_KEY)
    assert isinstance(receipt, bytes)
    assert len(receipt) > 0


def test_generate_receipt_contains_command_id(handler):
    cmd = handler.issue(AGENT_ID, "PAUSE", "reason", ISSUER_ID, OPERATOR_KEY)
    receipt = handler.generate_receipt(cmd, AGENT_KEY)
    data = json.loads(receipt.decode("utf-8"))
    assert data["command_id"] == cmd.command_id


def test_generate_receipt_contains_agent_id(handler):
    cmd = handler.issue(AGENT_ID, "STOP", "halt", ISSUER_ID, OPERATOR_KEY)
    receipt = handler.generate_receipt(cmd, AGENT_KEY)
    data = json.loads(receipt.decode("utf-8"))
    expected_agent_id = hashlib.sha256(AGENT_KEY).hexdigest()
    assert data["agent_id"] == expected_agent_id


def test_generate_receipt_status_honored(handler):
    cmd = handler.issue(AGENT_ID, "PAUSE", "reason", ISSUER_ID, OPERATOR_KEY)
    receipt = handler.generate_receipt(cmd, AGENT_KEY)
    data = json.loads(receipt.decode("utf-8"))
    assert data["status"] == "HONORED"


def test_generate_receipt_has_signature(handler):
    cmd = handler.issue(AGENT_ID, "RESUME", "ok", ISSUER_ID, OPERATOR_KEY)
    receipt = handler.generate_receipt(cmd, AGENT_KEY)
    data = json.loads(receipt.decode("utf-8"))
    assert "signature" in data
    assert len(data["signature"]) == 64  # 32 bytes hex = 64 chars
