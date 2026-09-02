"""Append-Only Audit Trail Logging Engine.

Maintains an immutable, structured JSON Lines (JSONL) ledger of every diagnostic,
policy, guardrail, outreach, and recovery decision made by the system.
"""

from datetime import datetime, timezone
import json
import os
from typing import Dict, Any, List, Optional


DEFAULT_AUDIT_LOG_PATH = "logs/audit_trail.jsonl"


def log_decision(
    transaction: Dict[str, Any],
    root_cause: str,
    policy_decision: Dict[str, Any],
    guardrail_result: Dict[str, Any],
    outreach_message: Optional[str] = None,
    outcome: Optional[Dict[str, Any]] = None,
    log_path: str = DEFAULT_AUDIT_LOG_PATH,
) -> Dict[str, Any]:
    """Append a structured decision record to the audit trail log.

    Args:
        transaction: Full transaction dictionary.
        root_cause: Diagnosed root cause string.
        policy_decision: Action and retry policy chosen.
        guardrail_result: Guardrail evaluation containing 'allowed' and 'reason'.
        outreach_message: Hinglish message text if drafted/sent, else None.
        outcome: Simulated recovery outcome dict or None.
        log_path: Filepath to the audit JSONL file.

    Returns:
        The exact dictionary logged to the file.
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    was_allowed = bool(guardrail_result.get("allowed", False))
    block_reason = None if was_allowed else guardrail_result.get("reason", "blocked by guardrail")

    entry: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transaction_id": transaction.get("transaction_id"),
        "subscription_id": transaction.get("subscription_id"),
        "customer_id": transaction.get("customer_id"),
        "customer_name": transaction.get("customer_name"),
        "amount_inr": transaction.get("amount_inr"),
        "due_date": transaction.get("due_date"),
        "failure_code": transaction.get("failure_code"),
        "root_cause": root_cause,
        "chosen_action": policy_decision.get("action"),
        "was_allowed": was_allowed,
        "block_reason": block_reason,
        "outreach_message": outreach_message,
        "outcome": outcome,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def load_audit_trail(log_path: str = DEFAULT_AUDIT_LOG_PATH) -> List[Dict[str, Any]]:
    """Load and parse all records from the audit trail JSONL log file.

    Args:
        log_path: Filepath to the audit JSONL file.

    Returns:
        List of audit record dictionaries in chronological order.
    """
    if not os.path.exists(log_path):
        return []

    records: List[Dict[str, Any]] = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                try:
                    records.append(json.loads(line_str))
                except json.JSONDecodeError:
                    continue

    return records


def clear_audit_trail(log_path: str = DEFAULT_AUDIT_LOG_PATH) -> None:
    """Clear or initialize the audit trail file for a fresh batch execution."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        pass
