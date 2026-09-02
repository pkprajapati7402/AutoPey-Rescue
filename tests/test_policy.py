"""Tests for Intervention Policy Engine."""

import pytest
from src.policy import decide_action, POLICY_TABLE


def test_decide_action_technical():
    """Verify policy for 'technical' root cause."""
    dummy_txn = {"transaction_id": "TXN00001"}
    decision = decide_action(dummy_txn, "technical")
    assert decision["action"] == "AUTO_RETRY"
    assert decision["max_retries"] == 2
    assert decision["min_gap_hours"] == 4


def test_decide_action_balance():
    """Verify policy for 'balance' root cause."""
    dummy_txn = {"transaction_id": "TXN00002"}
    decision = decide_action(dummy_txn, "balance")
    assert decision["action"] == "HOLD_AND_NUDGE"
    assert decision["max_retries"] == 2
    assert decision["min_gap_hours"] == 48


def test_decide_action_expired():
    """Verify policy for 'expired' root cause."""
    dummy_txn = {"transaction_id": "TXN00003"}
    decision = decide_action(dummy_txn, "expired")
    assert decision["action"] == "REAUTH_LINK"
    assert decision["max_retries"] == 1
    assert decision["min_gap_hours"] is None


def test_decide_action_terminal():
    """Verify policy for 'terminal' root cause."""
    dummy_txn = {"transaction_id": "TXN00004"}
    decision = decide_action(dummy_txn, "terminal")
    assert decision["action"] == "STOP_AND_FLAG"
    assert decision["max_retries"] == 0
    assert decision["min_gap_hours"] is None


def test_decide_action_invalid_root_cause():
    """Verify ValueError is raised on unknown root_cause."""
    dummy_txn = {"transaction_id": "TXN00005"}
    with pytest.raises(ValueError, match="Unrecognized root_cause"):
        decide_action(dummy_txn, "invalid_cause")
