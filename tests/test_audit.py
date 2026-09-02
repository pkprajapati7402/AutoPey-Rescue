"""Tests for Audit Trail Logging and Loading."""

import os
import tempfile
import pytest
from src.audit import log_decision, load_audit_trail, clear_audit_trail


def test_log_and_load_audit_trail():
    """Verify log_decision appends correctly and load_audit_trail parses JSONL accurately."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        sample_txn = {
            "transaction_id": "TXN00100",
            "subscription_id": "SUB00100",
            "customer_id": "CUST00100",
            "customer_name": "Pooja Patel",
            "amount_inr": 999,
            "due_date": "2026-08-25",
            "failure_code": "INSUFFICIENT_BALANCE",
        }
        policy = {"action": "HOLD_AND_NUDGE", "max_retries": 2, "min_gap_hours": 48}
        guardrail_allow = {"allowed": True, "reason": "within policy limits"}
        outreach = "Hi Pooja! Apka Rs.999 payment process nahi hua."

        entry1 = log_decision(
            transaction=sample_txn,
            root_cause="balance",
            policy_decision=policy,
            guardrail_result=guardrail_allow,
            outreach_message=outreach,
            log_path=tmp_path,
        )

        guardrail_block = {"allowed": False, "reason": "customer opted out"}
        entry2 = log_decision(
            transaction=sample_txn,
            root_cause="balance",
            policy_decision=policy,
            guardrail_result=guardrail_block,
            outreach_message=None,
            log_path=tmp_path,
        )

        loaded = load_audit_trail(tmp_path)
        assert len(loaded) == 2
        assert loaded[0]["transaction_id"] == "TXN00100"
        assert loaded[0]["was_allowed"] is True
        assert loaded[0]["block_reason"] is None
        assert loaded[0]["outreach_message"] == outreach

        assert loaded[1]["was_allowed"] is False
        assert loaded[1]["block_reason"] == "customer opted out"
        assert loaded[1]["outreach_message"] is None

        clear_audit_trail(tmp_path)
        assert len(load_audit_trail(tmp_path)) == 0

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
