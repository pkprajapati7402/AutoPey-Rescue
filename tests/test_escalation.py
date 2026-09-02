"""Tests for the Escalation Engine.

Covers all 5 escalation paths: DECLINED_STOP, PROMISE_BROKEN, RETRY_SCHEDULED,
HUMAN_REVIEW, and edge cases.
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.escalation import classify_escalation, get_escalation_summary, log_escalation, load_escalation_queue


SAMPLE_TXN = {
    "transaction_id": "TXN_TEST_001",
    "customer_id": "CUST001",
    "customer_name": "Ananya Verma",
    "amount_inr": 499,
    "failure_code": "INSUFFICIENT_BALANCE",
}


def test_escalation_declined_stop():
    """DECLINED reply → DECLINED_STOP path with HIGH priority."""
    promise_result = {"status": "DECLINED", "promised_date": None}
    result = classify_escalation(SAMPLE_TXN, promise_result)
    assert result["escalation_path"] == "DECLINED_STOP"
    assert result["priority"] == "HIGH"
    assert "stop" in result["next_action"].lower() or "crm" in result["next_action"].lower()


def test_escalation_promised_with_date_not_breached():
    """PROMISED with future date → RETRY_SCHEDULED path."""
    # Use a date far in the future so it's definitely not breached
    promise_result = {"status": "PROMISED", "promised_date": "2030-01-01"}
    result = classify_escalation(SAMPLE_TXN, promise_result, days_since_contact=1.0)
    assert result["escalation_path"] == "RETRY_SCHEDULED"
    assert result["priority"] == "LOW"


def test_escalation_promised_broken():
    """PROMISED with past date and many days elapsed → PROMISE_BROKEN with HIGH priority."""
    promise_result = {"status": "PROMISED", "promised_date": "2020-01-01"}
    result = classify_escalation(SAMPLE_TXN, promise_result, days_since_contact=10.0)
    assert result["escalation_path"] == "PROMISE_BROKEN"
    assert result["priority"] == "HIGH"


def test_escalation_promised_no_date():
    """PROMISED without a specific date → RETRY_SCHEDULED, MEDIUM priority."""
    promise_result = {"status": "PROMISED", "promised_date": None}
    result = classify_escalation(SAMPLE_TXN, promise_result)
    assert result["escalation_path"] == "RETRY_SCHEDULED"
    assert result["priority"] == "MEDIUM"


def test_escalation_unclear():
    """UNCLEAR reply → HUMAN_REVIEW path."""
    promise_result = {"status": "UNCLEAR", "promised_date": None}
    result = classify_escalation(SAMPLE_TXN, promise_result)
    assert result["escalation_path"] == "HUMAN_REVIEW"
    assert result["priority"] == "MEDIUM"


def test_escalation_summary():
    """Escalation summary computes correct counts."""
    records = [
        {"escalation_path": "DECLINED_STOP", "priority": "HIGH", "amount_inr": 499},
        {"escalation_path": "RETRY_SCHEDULED", "priority": "LOW", "amount_inr": 299},
        {"escalation_path": "HUMAN_REVIEW", "priority": "MEDIUM", "amount_inr": 199},
        {"escalation_path": "PROMISE_BROKEN", "priority": "HIGH", "amount_inr": 999},
    ]
    summary = get_escalation_summary(records)
    assert summary["total_escalations"] == 4
    assert summary["high_priority_count"] == 2
    assert summary["by_path"]["DECLINED_STOP"] == 1
    assert summary["declined_amount_inr"] == 499


def test_escalation_log_and_load():
    """Log and reload escalation records correctly."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
        path = f.name

    try:
        promise_result = {"status": "DECLINED", "promised_date": None}
        escalation = classify_escalation(SAMPLE_TXN, promise_result)
        log_escalation(SAMPLE_TXN, escalation, promise_result, log_path=path)

        records = load_escalation_queue(log_path=path)
        assert len(records) == 1
        assert records[0]["transaction_id"] == "TXN_TEST_001"
        assert records[0]["escalation_path"] == "DECLINED_STOP"
    finally:
        os.unlink(path)
