"""Intervention Policy Engine for Failed Mandate Transactions.

Decides the strategic intervention parameters (action type, maximum retry count,
and minimum cooldown gap) based on the diagnosed root cause.

NOTE: This module strictly defines the intended policy mapping. It does NOT enforce
dynamic runtime constraints (such as opt-out status, prior attempt history, or
cooldown checks) — runtime safety and enforcement are handled by guardrails.py.
"""

from typing import Dict, Any, Optional

# Root cause intervention policy definitions
POLICY_TABLE = {
    "technical": {
        "action": "AUTO_RETRY",
        "max_retries": 2,
        "min_gap_hours": 4,
        "description": "Transient infrastructure timeout. Auto-retry within the day after a short cooldown."
    },
    "balance": {
        "action": "HOLD_AND_NUDGE",
        "max_retries": 2,
        "min_gap_hours": 48,
        "description": "Insufficient balance. Hold retry, send personalized Hinglish nudge, and align with salary cycle."
    },
    "expired": {
        "action": "REAUTH_LINK",
        "max_retries": 1,
        "min_gap_hours": None,
        "description": "Mandate has expired or requires renewal. Send mandate re-authorization link without blind debit retries."
    },
    "terminal": {
        "action": "STOP_AND_FLAG",
        "max_retries": 0,
        "min_gap_hours": None,
        "description": "Hard decline or user cancellation. Cease automated retries immediately and flag for customer support review."
    },
}


def decide_action(transaction: Dict[str, Any], root_cause: str) -> Dict[str, Any]:
    """Determine the intervention policy for a given root cause.

    Args:
        transaction: The transaction record dictionary.
        root_cause: The diagnosed root cause category string.

    Returns:
        Dict with keys:
        - 'action': string identifier of the intervention
        - 'max_retries': integer limit on retries
        - 'min_gap_hours': integer hours or None
        - 'description': human-readable summary of the policy

    Raises:
        ValueError: If the root_cause is not recognized.
    """
    if root_cause not in POLICY_TABLE:
        raise ValueError(
            f"Unrecognized root_cause '{root_cause}'. "
            f"Expected one of: {list(POLICY_TABLE.keys())}"
        )

    policy = POLICY_TABLE[root_cause]
    return {
        "action": policy["action"],
        "max_retries": policy["max_retries"],
        "min_gap_hours": policy["min_gap_hours"],
        "description": policy["description"],
    }
