"""Metrics and Performance Analysis Engine.

Calculates key performance indicators (KPIs) comparing intelligent root-cause
recovery against naive blind-retry baselines:
- Recovery Rate (%)
- Total Portfolio ₹ Recovered
- Total Customer Contacts
- Recovered ₹ per Contact (Core Efficiency Ratio)
- Average Days to Recovery
"""

from typing import List, Dict, Any


def compute_metrics(outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute comprehensive revenue recovery metrics from a list of simulation outcomes.

    Args:
        outcomes: List of outcome dictionaries containing:
            - 'transaction_id': str
            - 'amount_inr': int
            - 'recovered': bool
            - 'recovered_amount_inr': int
            - 'contacts_sent': int
            - 'days_to_recovery': Optional[float]

    Returns:
        Dict of computed KPI metrics.
    """
    total_txns = len(outcomes)
    if total_txns == 0:
        return {
            "total_transactions": 0,
            "recovered_transactions": 0,
            "recovery_rate_pct": 0.0,
            "total_at_risk_inr": 0,
            "total_recovered_inr": 0,
            "revenue_recovery_rate_pct": 0.0,
            "total_contacts": 0,
            "recovered_per_contact": 0.0,
            "avg_days_to_recovery": 0.0,
        }

    total_at_risk = sum(o.get("amount_inr", 0) for o in outcomes)
    recovered_outcomes = [o for o in outcomes if o.get("recovered", False)]
    recovered_count = len(recovered_outcomes)
    total_recovered = sum(o.get("recovered_amount_inr", 0) for o in recovered_outcomes)
    total_contacts = sum(o.get("contacts_sent", 0) for o in outcomes)

    recovery_rate_pct = round((recovered_count / total_txns) * 100, 2)
    revenue_recovery_rate_pct = (
        round((total_recovered / total_at_risk) * 100, 2) if total_at_risk > 0 else 0.0
    )

    recovered_per_contact = (
        round(total_recovered / total_contacts, 2) if total_contacts > 0 else 0.0
    )

    recovery_days_list = [
        o["days_to_recovery"]
        for o in recovered_outcomes
        if o.get("days_to_recovery") is not None
    ]
    avg_days_to_recovery = (
        round(sum(recovery_days_list) / len(recovery_days_list), 2)
        if recovery_days_list
        else 0.0
    )

    return {
        "total_transactions": total_txns,
        "recovered_transactions": recovered_count,
        "recovery_rate_pct": recovery_rate_pct,
        "total_at_risk_inr": total_at_risk,
        "total_recovered_inr": total_recovered,
        "revenue_recovery_rate_pct": revenue_recovery_rate_pct,
        "total_contacts": total_contacts,
        "recovered_per_contact": recovered_per_contact,
        "avg_days_to_recovery": avg_days_to_recovery,
    }
