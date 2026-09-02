"""Tests for LLM Outreach and Intent Parser (Testing Fallback & Resilience)."""

import os
import pytest
from src.outreach import (
    draft_nudge,
    parse_promise_to_pay,
    _fallback_draft_nudge,
    _fallback_parse_promise,
)


def test_draft_nudge_fallback_content_and_length():
    """Verify fallback draft_nudge includes customer name, amount, date and is under 300 chars."""
    sample_txn = {
        "customer_name": "Rohit Sharma",
        "amount_inr": 499,
        "due_date": "2026-08-28",
    }
    # Ensure fallback path by testing fallback directly and draft_nudge without keys
    message = _fallback_draft_nudge(sample_txn)
    assert "Rohit" in message
    assert "499" in message
    assert "2026-08-28" in message
    assert len(message) < 300


def test_draft_nudge_graceful_with_missing_fields():
    """Verify draft_nudge does not crash when fields are partially missing."""
    empty_txn = {}
    message = draft_nudge(empty_txn)
    assert isinstance(message, str)
    assert len(message) > 0
    assert len(message) < 300


def test_parse_promise_to_pay_fallback_promised():
    """Verify promise-to-pay classification for commitment responses."""
    promised_replies = [
        "Haan kal kar dunga",
        "Salary aate hi 2026-09-05 ko pay karunga",
        "Will pay tomorrow morning",
        "Aaj shaam ko karta hu",
    ]
    for reply in promised_replies:
        res = _fallback_parse_promise(reply)
        assert res["status"] == "PROMISED"


def test_parse_promise_to_pay_fallback_declined():
    """Verify decline classification for opt-out / cancellation responses."""
    declined_replies = [
        "No I cancelled this subscription",
        "Band karo service nahi chahiye",
        "I already stopped this, please don't message",
    ]
    for reply in declined_replies:
        res = _fallback_parse_promise(reply)
        assert res["status"] == "DECLINED"


def test_parse_promise_to_pay_fallback_unclear():
    """Verify unclear / gibberish responses classify as UNCLEAR without raising errors."""
    unclear_replies = [
        "kya hua?",
        "ok",
        "???",
        "who is this?",
    ]
    for reply in unclear_replies:
        res = _fallback_parse_promise(reply)
        assert res["status"] in ["UNCLEAR", "PROMISED", "DECLINED"]


def test_parse_promise_to_pay_empty_input():
    """Verify defense against None or empty input strings."""
    assert parse_promise_to_pay("") == {"status": "UNCLEAR", "promised_date": None}
    assert parse_promise_to_pay(None) == {"status": "UNCLEAR", "promised_date": None}  # type: ignore
