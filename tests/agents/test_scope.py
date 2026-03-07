"""
Tests for blackhorse.agents.scope — ScopeValidator.

Covers:
- create_scope() produces an unsigned AgentScope
- sign_scope() populates the signature field
- validate() returns True for a permitted action
- validate() returns False for a prohibited action (even if also permitted)
- validate() returns False for actions not in either list
- validate() returns False for unsigned scope
- flag_deviation() returns signed JSON bytes
- flag_deviation() references the correct scope_id and decision_id
- AgentScope.to_dict() / from_dict() round-trip
"""

import hashlib
import json

import pytest

from blackhorse.agents.scope import AgentScope, DeviationReport, ScopeValidator


OPERATOR_KEY = b"\xAA" * 32
AGENT_KEY = b"\xBB" * 32
AGENT_ID = hashlib.sha256(AGENT_KEY).hexdigest()

PERMITTED = ["relay_message", "read_queue", "scan_nodes"]
PROHIBITED = ["write_disk", "broadcast_unencrypted", "modify_scope"]


@pytest.fixture
def validator():
    return ScopeValidator()


@pytest.fixture
def unsigned_scope(validator):
    return validator.create_scope(
        agent_id=AGENT_ID,
        version="1.0.0",
        permitted_actions=PERMITTED,
        prohibited_actions=PROHIBITED,
        max_autonomy_seconds=300,
        data_access_scope=["queue.db"],
        output_destinations=["udp://mesh"],
    )


@pytest.fixture
def signed_scope(validator, unsigned_scope):
    return validator.sign_scope(unsigned_scope, OPERATOR_KEY)


# ---------------------------------------------------------------------------
# create_scope
# ---------------------------------------------------------------------------

def test_create_scope_fields(unsigned_scope):
    assert unsigned_scope.agent_id == AGENT_ID
    assert unsigned_scope.version == "1.0.0"
    assert "relay_message" in unsigned_scope.permitted_actions
    assert "write_disk" in unsigned_scope.prohibited_actions
    assert unsigned_scope.max_autonomy_seconds == 300
    assert unsigned_scope.signature == b""


def test_create_scope_generates_unique_scope_id(validator):
    s1 = validator.create_scope(AGENT_ID, "1.0.0", [], [], 60, [], [])
    s2 = validator.create_scope(AGENT_ID, "1.0.0", [], [], 60, [], [])
    assert s1.scope_id != s2.scope_id


# ---------------------------------------------------------------------------
# sign_scope
# ---------------------------------------------------------------------------

def test_sign_scope_populates_signature(unsigned_scope, validator):
    scope = validator.sign_scope(unsigned_scope, OPERATOR_KEY)
    assert scope.signature != b""
    assert len(scope.signature) == 32


def test_sign_scope_is_same_object(unsigned_scope, validator):
    scope = validator.sign_scope(unsigned_scope, OPERATOR_KEY)
    assert scope is unsigned_scope


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def test_validate_permitted_action_approved(validator, signed_scope):
    ok, reason = validator.validate("relay_message", signed_scope, OPERATOR_KEY)
    assert ok
    assert reason == "APPROVED"


def test_validate_prohibited_action_denied(validator, signed_scope):
    ok, reason = validator.validate("write_disk", signed_scope, OPERATOR_KEY)
    assert not ok
    assert "PROHIBITED" in reason


def test_validate_unknown_action_denied(validator, signed_scope):
    ok, reason = validator.validate("fly_to_mars", signed_scope, OPERATOR_KEY)
    assert not ok
    assert "NOT_PERMITTED" in reason


def test_validate_prohibited_overrides_permitted(validator):
    scope = ScopeValidator.create_scope(
        agent_id=AGENT_ID,
        version="1.0.0",
        permitted_actions=["ambiguous_action"],
        prohibited_actions=["ambiguous_action"],
        max_autonomy_seconds=60,
        data_access_scope=[],
        output_destinations=[],
    )
    validator.sign_scope(scope, OPERATOR_KEY)
    ok, reason = validator.validate("ambiguous_action", scope, OPERATOR_KEY)
    assert not ok
    assert "PROHIBITED" in reason


def test_validate_unsigned_scope_fails(validator, unsigned_scope):
    ok, reason = validator.validate("relay_message", unsigned_scope, OPERATOR_KEY)
    assert not ok
    assert "SCOPE_SIGNATURE_INVALID" in reason


def test_validate_wrong_key_fails(validator, signed_scope):
    wrong_key = b"\x00" * 32
    ok, reason = validator.validate("relay_message", signed_scope, wrong_key)
    assert not ok
    assert "SCOPE_SIGNATURE_INVALID" in reason


# ---------------------------------------------------------------------------
# flag_deviation
# ---------------------------------------------------------------------------

def test_flag_deviation_returns_bytes(validator, signed_scope):
    report_bytes = validator.flag_deviation(
        "write_disk", signed_scope, "decision-id-xyz", AGENT_KEY
    )
    assert isinstance(report_bytes, bytes)


def test_flag_deviation_json_contains_expected_fields(validator, signed_scope):
    report_bytes = validator.flag_deviation(
        "write_disk", signed_scope, "decision-id-xyz", AGENT_KEY
    )
    data = json.loads(report_bytes.decode("utf-8"))
    assert data["scope_id"] == signed_scope.scope_id
    assert data["decision_id"] == "decision-id-xyz"
    assert data["action"] == "write_disk"
    assert "signature" in data
    assert data["agent_id"] == AGENT_ID


def test_flag_deviation_has_signature(validator, signed_scope):
    report_bytes = validator.flag_deviation(
        "write_disk", signed_scope, "decision-id-xyz", AGENT_KEY
    )
    data = json.loads(report_bytes.decode("utf-8"))
    assert len(data["signature"]) == 64  # 32 bytes as hex


# ---------------------------------------------------------------------------
# AgentScope serialisation
# ---------------------------------------------------------------------------

def test_scope_to_dict_from_dict_round_trip(signed_scope):
    d = signed_scope.to_dict()
    restored = AgentScope.from_dict(d)
    assert restored.scope_id == signed_scope.scope_id
    assert restored.agent_id == signed_scope.agent_id
    assert restored.permitted_actions == signed_scope.permitted_actions
    assert restored.prohibited_actions == signed_scope.prohibited_actions
    assert restored.signature == signed_scope.signature
