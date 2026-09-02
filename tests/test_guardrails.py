"""Tests for Safety Guardrails and Stopping Rules."""

from datetime import datetime, timezone, timedelta
import pytest
from src.guardrails import is_action_allowed, check_global_cap


def test_guardrail_rule1_opted_out():
    """Rule 1: Opted-out customer is blocked immediately."""
    txn = {"opted_out": True}
    policy = {"action": "HOLD_AND_NUDGE", "max_retries": 2, "min_gap_hours": 48}
    res = is_action_allowed(txn, policy, contact_history=[])
    assert res["allowed"] is False
    assert res["reason"] == "customer opted out"


def test_guardrail_rule2_terminal_action():
    """Rule 2: Terminal category action (STOP_AND_FLAG) is blocked."""
    txn = {"opted_out": False}
    policy = {"action": "STOP_AND_FLAG", "max_retries": 0, "min_gap_hours": None}
    res = is_action_allowed(txn, policy, contact_history=[])
    assert res["allowed"] is False
    assert res["reason"] == "terminal category, no contact permitted"


def test_guardrail_rule3_max_retries_reached():
    """Rule 3: Contact history reaching or exceeding max_retries is blocked."""
    txn = {"opted_out": False}
    policy = {"action": "HOLD_AND_NUDGE", "max_retries": 2, "min_gap_hours": 48}
    history = [
        {"timestamp": "2026-08-20T10:00:00Z"},
        {"timestamp": "2026-08-23T10:00:00Z"}
    ]
    res = is_action_allowed(txn, policy, contact_history=history)
    assert res["allowed"] is False
    assert res["reason"] == "max retries reached"


def test_guardrail_rule4_cooldown_active():
    """Rule 4: Contact attempted before min_gap_hours elapsed is blocked."""
    txn = {"opted_out": False}
    policy = {"action": "AUTO_RETRY", "max_retries": 2, "min_gap_hours": 4}

    # Last contact was 2 hours ago (less than 4 hours min gap)
    base_time = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    last_contact_time = base_time - timedelta(hours=2)
    history = [{"timestamp": last_contact_time.isoformat()}]

    res = is_action_allowed(txn, policy, contact_history=history, current_time=base_time)
    assert res["allowed"] is False
    assert res["reason"] == "cooldown period active"


def test_guardrail_rule5_allowed_within_limits():
    """Rule 5: Allowed when cooldown has passed and retries are under limit."""
    txn = {"opted_out": False}
    policy = {"action": "AUTO_RETRY", "max_retries": 2, "min_gap_hours": 4}

    # Last contact was 6 hours ago (greater than 4 hours min gap)
    base_time = datetime(2026, 8, 28, 12, 0, 0, tzinfo=timezone.utc)
    last_contact_time = base_time - timedelta(hours=6)
    history = [{"timestamp": last_contact_time.isoformat()}]

    res = is_action_allowed(txn, policy, contact_history=history, current_time=base_time)
    assert res["allowed"] is True
    assert res["reason"] == "within policy limits"


def test_check_global_cap():
    """Verify global cap function thresholds."""
    assert check_global_cap(nudges_sent_today=49, cap=50) is True
    assert check_global_cap(nudges_sent_today=50, cap=50) is False
    assert check_global_cap(nudges_sent_today=51, cap=50) is False
