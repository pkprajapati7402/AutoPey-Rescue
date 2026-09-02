"""Tests for Deterministic Diagnosis Engine."""

import pytest
from src.diagnosis import diagnose


def test_diagnose_all_valid_categories():
    """Verify each valid failure_code correctly maps to its root_cause category."""
    test_cases = [
        ({"failure_code": "TECH_TIMEOUT"}, "technical"),
        ({"failure_code": "INSUFFICIENT_BALANCE"}, "balance"),
        ({"failure_code": "MANDATE_EXPIRED"}, "expired"),
        ({"failure_code": "HARD_DECLINE_OR_CANCELLED"}, "terminal"),
    ]

    for txn, expected in test_cases:
        assert diagnose(txn) == expected


def test_diagnose_unrecognized_failure_code():
    """Verify ValueError is raised when failure_code is unknown."""
    with pytest.raises(ValueError, match="Unrecognized failure_code"):
        diagnose({"failure_code": "UNKNOWN_ERROR_CODE"})


def test_diagnose_missing_failure_code():
    """Verify ValueError is raised when failure_code is missing."""
    with pytest.raises(ValueError, match="missing 'failure_code'"):
        diagnose({"transaction_id": "TXN0001"})


def test_diagnose_invalid_input_type():
    """Verify ValueError is raised when input is not a dict."""
    with pytest.raises(ValueError, match="Expected transaction to be a dict"):
        diagnose("not-a-dict")  # type: ignore
