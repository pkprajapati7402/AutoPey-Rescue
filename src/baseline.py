"""Naive Blind-Retry Baseline Simulation Engine.

Simulates the legacy industry practice:
- Blindly retrying every failed mandate every 24 hours up to 3 times.
- Dispatching the identical generic notification on every attempt.
- Zero root-cause intelligence, no cooldown adjustments, and ignoring opt-outs until retries run out.
"""

import random
from typing import List, Dict, Any

# Blind retry recovery probabilities per individual attempt
BASELINE_RECOVERY_PROBABILITIES = {
    "TECH_TIMEOUT": 0.70,              # Transient glitch can resolve on retry
    "INSUFFICIENT_BALANCE": 0.30,      # Blind next-day retry rarely catches funds
    "MANDATE_EXPIRED": 0.05,           # Retrying an expired mandate almost always fails
    "HARD_DECLINE_OR_CANCELLED": 0.00, # Terminal cancellation will never succeed
}

MAX_BASELINE_ATTEMPTS = 3


def run_baseline(
    transactions: List[Dict[str, Any]],
    seed: int = 42
) -> List[Dict[str, Any]]:
    """Simulate naive blind retries across a batch of failed transactions.

    Args:
        transactions: List of transaction dictionaries.
        seed: Random seed for deterministic simulation.

    Returns:
        List of outcome dictionaries per transaction.
    """
    rng = random.Random(seed)
    outcomes: List[Dict[str, Any]] = []

    for txn in transactions:
        txn_id = txn["transaction_id"]
        failure_code = txn.get("failure_code", "UNKNOWN")
        amount = txn.get("amount_inr", 0)
        prob = BASELINE_RECOVERY_PROBABILITIES.get(failure_code, 0.10)

        recovered = False
        attempts_made = 0
        days_to_recovery = None

        for attempt in range(1, MAX_BASELINE_ATTEMPTS + 1):
            attempts_made += 1
            # Check if this blind attempt succeeds
            if rng.random() < prob:
                recovered = True
                days_to_recovery = float(attempt)  # 24h intervals (1 day, 2 days, 3 days)
                break

        outcome = {
            "transaction_id": txn_id,
            "failure_code": failure_code,
            "amount_inr": amount,
            "recovered": recovered,
            "recovered_amount_inr": amount if recovered else 0,
            "attempts_made": attempts_made,
            "contacts_sent": attempts_made,  # Generic message sent on every attempt
            "days_to_recovery": days_to_recovery,
            "policy": "NAIVE_BLIND_RETRY",
        }
        outcomes.append(outcome)

    return outcomes
