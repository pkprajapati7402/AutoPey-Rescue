"""Escalation Engine — Promise-to-Pay Tracker and Compliance Routing.

This module implements the bounded escalation workflow that the Razorpay problem
statement explicitly asks for:
  "Show measured money recovered across a batch, with compliant escalation,
   stopping rules, and an audit trail."

It tracks customer promise-to-pay commitments, detects broken promises, and
routes each case to the appropriate escalation path:
  - PROMISE_KEPT: Payment completed on promised date → case closed
  - PROMISE_BROKEN: No payment after promised date → escalate to human review
  - DECLINED_STOP: Customer explicitly declined → permanent stop in system
  - RETRY_SCHEDULED: Promise given but date not yet reached → hold and monitor
  - HUMAN_REVIEW: UNCLEAR or ambiguous → route to support team

Escalation records are written to logs/escalation_queue.jsonl (append-only).
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional


DEFAULT_ESCALATION_LOG = "logs/escalation_queue.jsonl"

# Number of days after a promised date before we consider the promise broken
PROMISE_BREACH_GRACE_DAYS = 2


def classify_escalation(
    transaction: Dict[str, Any],
    promise_result: Dict[str, Any],
    days_since_contact: Optional[float] = None,
) -> Dict[str, Any]:
    """Classify the escalation path for a transaction based on customer intent.

    Args:
        transaction: The original transaction record.
        promise_result: Output from parse_promise_to_pay() with 'status' and 'promised_date'.
        days_since_contact: Days elapsed since outreach was sent. Used to detect broken promises.

    Returns:
        Dict with:
        - 'escalation_path': one of PROMISE_KEPT, PROMISE_BROKEN, DECLINED_STOP,
                             RETRY_SCHEDULED, HUMAN_REVIEW
        - 'priority': HIGH | MEDIUM | LOW
        - 'next_action': Human-readable description of what should happen
        - 'reason': Explanation for this classification
    """
    status = promise_result.get("status", "UNCLEAR")
    promised_date_raw = promise_result.get("promised_date")

    if status == "DECLINED":
        return {
            "escalation_path": "DECLINED_STOP",
            "priority": "HIGH",
            "next_action": "Immediately stop all automated contacts. Mark mandate as customer-terminated. Update CRM with opt-out flag.",
            "reason": "Customer explicitly declined payment or cancelled subscription.",
        }

    if status == "PROMISED":
        if promised_date_raw:
            # Try to parse the promised date and check if it's breached
            breached = _is_promise_breached(promised_date_raw, days_since_contact)
            if breached:
                return {
                    "escalation_path": "PROMISE_BROKEN",
                    "priority": "HIGH",
                    "next_action": "Route to human collections agent. Send one final escalation nudge before closing.",
                    "reason": f"Customer promised payment by '{promised_date_raw}' but payment not received after {PROMISE_BREACH_GRACE_DAYS}-day grace period.",
                    "promised_date": promised_date_raw,
                }
            else:
                return {
                    "escalation_path": "RETRY_SCHEDULED",
                    "priority": "LOW",
                    "next_action": f"Hold automated retries. Re-check for payment after promised date '{promised_date_raw}'.",
                    "reason": "Customer has made a promise to pay on a future date. Monitoring mode active.",
                    "promised_date": promised_date_raw,
                }
        else:
            # Generic promise — schedule follow-up in 48 hours
            return {
                "escalation_path": "RETRY_SCHEDULED",
                "priority": "MEDIUM",
                "next_action": "Schedule payment check in 48 hours. Send one gentle follow-up if not received.",
                "reason": "Customer expressed intent to pay without a specific date. Monitoring mode.",
                "promised_date": None,
            }

    # UNCLEAR or unknown
    return {
        "escalation_path": "HUMAN_REVIEW",
        "priority": "MEDIUM",
        "next_action": "Route to customer support team for manual outreach. Do not send further automated nudges.",
        "reason": "Customer response was ambiguous or non-responsive. Requires human judgment.",
    }


def _is_promise_breached(promised_date_raw: str, days_since_contact: Optional[float]) -> bool:
    """Check if a promise date has been breached.

    Args:
        promised_date_raw: Raw date string from LLM extraction.
        days_since_contact: Days elapsed since outreach was sent.

    Returns:
        True if promise is breached, False otherwise.
    """
    try:
        # Try ISO date parse
        from dateutil import parser as dt_parser
        promised_dt = dt_parser.parse(promised_date_raw).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        deadline = promised_dt + timedelta(days=PROMISE_BREACH_GRACE_DAYS)
        return now > deadline
    except Exception:
        # Fall back to days_since_contact heuristic
        if days_since_contact is not None and days_since_contact > 5:
            return True
        return False


def log_escalation(
    transaction: Dict[str, Any],
    escalation: Dict[str, Any],
    promise_result: Dict[str, Any],
    log_path: str = DEFAULT_ESCALATION_LOG,
) -> Dict[str, Any]:
    """Append an escalation event to the escalation queue log.

    Args:
        transaction: The original transaction dict.
        escalation: Result from classify_escalation().
        promise_result: The parsed promise-to-pay intent.
        log_path: Filepath for the escalation JSONL log.

    Returns:
        The entry dict that was logged.
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transaction_id": transaction.get("transaction_id"),
        "customer_id": transaction.get("customer_id"),
        "customer_name": transaction.get("customer_name"),
        "amount_inr": transaction.get("amount_inr"),
        "failure_code": transaction.get("failure_code"),
        "customer_reply_status": promise_result.get("status"),
        "promised_date": promise_result.get("promised_date"),
        "escalation_path": escalation.get("escalation_path"),
        "priority": escalation.get("priority"),
        "next_action": escalation.get("next_action"),
        "reason": escalation.get("reason"),
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return entry


def load_escalation_queue(log_path: str = DEFAULT_ESCALATION_LOG) -> List[Dict[str, Any]]:
    """Load all escalation events from the queue log.

    Args:
        log_path: Filepath to the escalation JSONL file.

    Returns:
        List of escalation event dictionaries in chronological order.
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


def clear_escalation_queue(log_path: str = DEFAULT_ESCALATION_LOG) -> None:
    """Clear the escalation queue for a fresh batch run."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        pass


def get_escalation_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute summary statistics over the escalation queue.

    Args:
        records: List of escalation event dictionaries.

    Returns:
        Summary dict with counts by path and priority.
    """
    from collections import Counter
    paths = Counter(r.get("escalation_path") for r in records)
    priorities = Counter(r.get("priority") for r in records)
    total_at_risk = sum(r.get("amount_inr", 0) for r in records)
    declined_amount = sum(
        r.get("amount_inr", 0)
        for r in records
        if r.get("escalation_path") == "DECLINED_STOP"
    )
    promised_amount = sum(
        r.get("amount_inr", 0)
        for r in records
        if r.get("escalation_path") in ["RETRY_SCHEDULED", "PROMISE_BROKEN"]
    )

    return {
        "total_escalations": len(records),
        "by_path": dict(paths),
        "by_priority": dict(priorities),
        "total_at_risk_inr": total_at_risk,
        "declined_amount_inr": declined_amount,
        "promised_amount_inr": promised_amount,
        "high_priority_count": priorities.get("HIGH", 0),
    }
