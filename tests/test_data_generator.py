"""Tests for Synthetic Data Generator."""

import os
import json
import tempfile
import pytest
from src.data_generator import (
    generate_synthetic_transactions,
    save_transactions,
    FAILURE_CODES,
)


def test_generate_synthetic_transactions_count():
    """Verify default and custom counts."""
    records_default = generate_synthetic_transactions(count=200, seed=42)
    assert len(records_default) == 200

    records_50 = generate_synthetic_transactions(count=50, seed=42)
    assert len(records_50) == 50


def test_generate_synthetic_transactions_fields():
    """Verify all required fields exist and have valid values/types."""
    records = generate_synthetic_transactions(count=100, seed=123)
    required_keys = {
        "transaction_id",
        "subscription_id",
        "customer_id",
        "customer_name",
        "amount_inr",
        "due_date",
        "failure_code",
        "attempt_number",
        "opted_out",
        "created_at",
    }

    for record in records:
        assert required_keys.issubset(record.keys())
        assert record["failure_code"] in FAILURE_CODES
        assert isinstance(record["amount_inr"], int)
        assert record["amount_inr"] > 0
        assert isinstance(record["opted_out"], bool)
        assert record["attempt_number"] == 1
        assert record["transaction_id"].startswith("TXN")
        assert len(record["customer_name"].split()) >= 2


def test_save_transactions():
    """Verify saving transactions to file and reading back correctly."""
    records = generate_synthetic_transactions(count=10, seed=99)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        save_transactions(records, output_path=tmp_path)
        assert os.path.exists(tmp_path)

        with open(tmp_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        assert len(loaded) == 10
        assert loaded[0]["transaction_id"] == records[0]["transaction_id"]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
