"""Safety Guardrails and Stopping Rules Engine.

Enforces financial compliance and customer protection boundaries:
- Immediate cessation on customer opt-out.
- Immediate block on terminal failure categories.
- Hard retry caps per failure category.
- Cooldown period enforcement between customer touches.
- Global batch spam protection cap.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from dateutil import parser as dt_parser


def parse_timestamp(ts: Union[str, datetime]) -> datetime:
    """Parse string or datetime to timezone-aware UTC datetime."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    dt = dt_parser.isoparse(ts)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_action_allowed(
    transaction: Dict[str, Any],
    policy_decision: Dict[str, Any],
    contact_history: List[Dict[str, Any]],
    current_time: Optional[Union[str, datetime]] = None,
) -> Dict[str, Any]:
    """Evaluate whether a proposed policy action is permitted under safety guardrails.

    Rules evaluated in strict order (first match wins):
    1. Opt-out check: If customer opted out -> NOT allowed.
    2. Terminal category: If policy action is STOP_AND_FLAG -> NOT allowed.
    3. Retry cap: If prior attempts >= max_retries -> NOT allowed.
    4. Cooldown window: If min_gap_hours is set and last touch < min_gap_hours ago -> NOT allowed.
    5. Pass: Otherwise -> ALLOWED.

    Args:
        transaction: Transaction details dict including 'opted_out'.
        policy_decision: Output from policy.decide_action with 'action', 'max_retries', 'min_gap_hours'.
        contact_history: List of prior contact events (each containing 'timestamp').
        current_time: Optional reference time for cooldown calculation (defaults to now).

    Returns:
        Dict with 'allowed' (bool) and 'reason' (str).
    """
    # Rule 1: Customer Opt-Out
    if transaction.get("opted_out", False) is True:
        return {
            "allowed": False,
            "reason": "customer opted out"
        }

    action = policy_decision.get("action")
    max_retries = policy_decision.get("max_retries", 0)
    min_gap_hours = policy_decision.get("min_gap_hours")

    # Rule 2: Terminal Category / Hard Stop
    if action == "STOP_AND_FLAG":
        return {
            "allowed": False,
            "reason": "terminal category, no contact permitted"
        }

    # Rule 3: Max Retries Cap
    if len(contact_history) >= max_retries:
        return {
            "allowed": False,
            "reason": "max retries reached"
        }

    # Rule 4: Cooldown Window Active
    if contact_history and min_gap_hours is not None:
        last_contact = contact_history[-1]
        last_ts_raw = last_contact.get("timestamp") if isinstance(last_contact, dict) else last_contact

        if last_ts_raw is not None:
            last_dt = parse_timestamp(last_ts_raw)
            ref_dt = parse_timestamp(current_time) if current_time is not None else datetime.now(timezone.utc)

            elapsed_hours = (ref_dt - last_dt).total_seconds() / 3600.0
            if elapsed_hours < min_gap_hours:
                return {
                    "allowed": False,
                    "reason": "cooldown period active"
                }

    # Rule 5: Within Policy Limits
    return {
        "allowed": True,
        "reason": "within policy limits"
    }


def check_global_cap(nudges_sent_today: int, cap: int = 50) -> bool:
    """Check if the global daily / batch outreach cap has been exceeded.

    Args:
        nudges_sent_today: Number of nudges already dispatched today.
        cap: Maximum allowable nudges per cycle (default: 50).

    Returns:
        True if within cap, False if cap has been reached or exceeded.
    """
    return nudges_sent_today < cap
