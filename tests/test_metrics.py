"""Tests for Metrics Calculation Engine."""

import pytest
from src.metrics import compute_metrics


def test_compute_metrics_hand_built():
    """Verify compute_metrics with hand-calculated expected values."""
    mock_outcomes = [
        {
            "transaction_id": "TXN001",
            "amount_inr": 500,
            "recovered": True,
            "recovered_amount_inr": 500,
            "contacts_sent": 1,
            "days_to_recovery": 1.0,
        },
        {
            "transaction_id": "TXN002",
            "amount_inr": 1000,
            "recovered": False,
            "recovered_amount_inr": 0,
            "contacts_sent": 3,
            "days_to_recovery": None,
        },
        {
            "transaction_id": "TXN003",
            "amount_inr": 1500,
            "recovered": True,
            "recovered_amount_inr": 1500,
            "contacts_sent": 2,
            "days_to_recovery": 3.0,
        },
    ]

    res = compute_metrics(mock_outcomes)

    # 2 out of 3 recovered = 66.67%
    assert res["total_transactions"] == 3
    assert res["recovered_transactions"] == 2
    assert res["recovery_rate_pct"] == 66.67

    # Total at risk = 500 + 1000 + 1500 = 3000
    assert res["total_at_risk_inr"] == 3000
    # Total recovered = 500 + 1500 = 2000
    assert res["total_recovered_inr"] == 2000
    assert res["revenue_recovery_rate_pct"] == 66.67

    # Total contacts = 1 + 3 + 2 = 6
    assert res["total_contacts"] == 6
    # Recovered per contact = 2000 / 6 = 333.33
    assert res["recovered_per_contact"] == 333.33

    # Avg days = (1.0 + 3.0) / 2 = 2.0
    assert res["avg_days_to_recovery"] == 2.0


def test_compute_metrics_empty_list():
    """Verify compute_metrics handles empty lists gracefully without ZeroDivisionError."""
    res = compute_metrics([])
    assert res["total_transactions"] == 0
    assert res["recovered_transactions"] == 0
    assert res["recovery_rate_pct"] == 0.0
    assert res["total_recovered_inr"] == 0
    assert res["total_contacts"] == 0
    assert res["recovered_per_contact"] == 0.0
    assert res["avg_days_to_recovery"] == 0.0
