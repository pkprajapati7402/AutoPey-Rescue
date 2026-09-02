"""Deterministic Diagnosis Engine for Failed Mandate Transactions.

ARCHITECTURAL RATIONALE:
------------------------
Why is this a rule-based lookup instead of an LLM call?
1. Determinism & Explainability: Bank and PSP error codes have strict, well-defined
   semantics. Using an LLM to classify standard codes introduces unnecessary latency,
   cost, and the risk of non-deterministic hallucinations in financial operations.
2. Production Safety: Financial recovery workflows require 100% auditability.
   Every diagnostic path must be mathematically verifiable by compliance and ops teams.
3. AI Judgment Principle: In this project, AI is deliberately used only where it
   earns its keep (natural Hinglish message drafting and free-form promise-to-pay intent
   extraction), keeping the diagnostic backbone fast, lightweight, and deterministic.
"""

from typing import Dict, Any

# Deterministic mapping table from standard failure codes to root cause categories
FAILURE_CODE_TO_ROOT_CAUSE = {
    "TECH_TIMEOUT": "technical",
    "INSUFFICIENT_BALANCE": "balance",
    "MANDATE_EXPIRED": "expired",
    "HARD_DECLINE_OR_CANCELLED": "terminal",
}


def diagnose(transaction: Dict[str, Any]) -> str:
    """Diagnose the root cause category for a failed transaction.

    Args:
        transaction: A dictionary containing at least the 'failure_code' key.

    Returns:
        The diagnosed root cause category string:
        'technical', 'balance', 'expired', or 'terminal'.

    Raises:
        ValueError: If failure_code is missing or unrecognized.
    """
    if not isinstance(transaction, dict):
        raise ValueError(f"Expected transaction to be a dict, got {type(transaction).__name__}")

    failure_code = transaction.get("failure_code")
    if not failure_code:
        raise ValueError("Transaction missing 'failure_code' field")

    if failure_code not in FAILURE_CODE_TO_ROOT_CAUSE:
        raise ValueError(
            f"Unrecognized failure_code '{failure_code}'. "
            f"Expected one of: {list(FAILURE_CODE_TO_ROOT_CAUSE.keys())}"
        )

    return FAILURE_CODE_TO_ROOT_CAUSE[failure_code]
