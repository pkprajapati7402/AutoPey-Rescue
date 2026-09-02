"""Integration tests for baseline and system execution pipelines."""

import os
import tempfile
import pytest
from src.baseline import run_baseline
from src.run_batch import run_system_pipeline
from src.metrics import compute_metrics
from src.data_generator import generate_synthetic_transactions


def test_baseline_pipeline_execution():
    """Verify baseline pipeline runs deterministically and produces valid outcomes."""
    sample_txns = generate_synthetic_transactions(count=20, seed=42)
    outcomes = run_baseline(sample_txns, seed=42)

    assert len(outcomes) == 20
    for o in outcomes:
        assert "recovered" in o
        assert "attempts_made" in o
        assert o["attempts_made"] >= 1
        assert o["attempts_made"] <= 3
        if o["recovered"]:
            assert o["recovered_amount_inr"] > 0
            assert o["days_to_recovery"] is not None
        else:
            assert o["recovered_amount_inr"] == 0

    metrics = compute_metrics(outcomes)
    assert metrics["total_transactions"] == 20
    assert metrics["recovery_rate_pct"] >= 0.0


def test_system_pipeline_execution():
    """Verify systemic intelligent pipeline runs, logs decisions, and adheres to limits."""
    sample_txns = generate_synthetic_transactions(count=20, seed=42)
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp_log = tmp.name
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp2:
        tmp_esc_log = tmp2.name

    try:
        outcomes = run_system_pipeline(
            sample_txns,
            seed=42,
            log_path=tmp_log,
            escalation_log_path=tmp_esc_log,
        )
        assert len(outcomes) == 20
        assert os.path.exists(tmp_log)
        assert os.path.exists(tmp_esc_log)

        metrics = compute_metrics(outcomes)
        assert metrics["total_transactions"] == 20

        # System efficiency check (fewer or targeted contacts)
        for o in outcomes:
            if o["chosen_action"] == "STOP_AND_FLAG":
                assert o["contacts_sent"] == 0
                assert o["attempts_made"] == 0

        # Verify new fields are present in outcomes
        for o in outcomes:
            assert "promise_to_pay_status" in o
            assert "escalation_path" in o
    finally:
        for path in [tmp_log, tmp_esc_log]:
            if os.path.exists(path):
                os.remove(path)
