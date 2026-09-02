"""Batch Execution Pipeline for AutoPey-Rescue.

Orchestrates the complete recovery loop across all synthetic transactions:
1. Deterministic Root-Cause Diagnosis
2. Intervention Policy Selection
3. Safety Guardrails & Stopping Rules Enforcement
4. LLM Outreach Generation (Google Gemini / Fallback)
5. Customer Promise-to-Pay Intent Simulation & Escalation Routing
6. Structured Append-Only Audit Trail Logging
7. Escalation Queue Logging for HOLD/REVIEW/STOP Cases
8. Comparative Simulation Benchmarking Against Naive Blind Retry Baseline
9. Metric Calculations & Export to data/results.json
"""

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List

# Ensure repository root is on sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.diagnosis import diagnose
from src.policy import decide_action
from src.guardrails import is_action_allowed, check_global_cap
from src.outreach import draft_nudge, parse_promise_to_pay, _fallback_draft_nudge, _fallback_parse_promise
from src.audit import log_decision, clear_audit_trail
from src.escalation import classify_escalation, log_escalation, clear_escalation_queue
from src.baseline import run_baseline
from src.metrics import compute_metrics
from src.data_generator import generate_synthetic_transactions, save_transactions


# Intelligent System Recovery Probabilities per targeted intervention
SYSTEM_RECOVERY_PROBABILITIES = {
    "technical": 0.88,  # Prompt same-day auto-retry resolves bank timeouts
    "balance": 0.68,    # 48h hold + Hinglish nudge aligned with salary cycle
    "expired": 0.42,    # Direct re-auth mandate link enables customer renewal
    "terminal": 0.00,   # Terminal decline - stop and flag to avoid spam
}

# Simulated customer reply distribution for nudged transactions (balance + expired)
# ~20% of nudged customers reply; of those: 55% promise, 25% decline, 20% unclear
PROMISE_REPLY_RATE = 0.20
PROMISE_STATUS_DIST = {
    "PROMISED": 0.55,
    "DECLINED": 0.25,
    "UNCLEAR": 0.20,
}

SIMULATED_REPLIES = {
    "PROMISED": [
        "Haan zaroor, kal kar dunga payment",
        "Salary aa rahi hai 5th ko, tab automatically ho jayega",
        "Aaj shaam 7 baje UPI se kar deta hun",
        "Yes will pay by end of week",
        "Ok ok, karunga 2-3 din mein",
    ],
    "DECLINED": [
        "Band karo ye subscription, mujhe nahi chahiye",
        "I have already cancelled this. Please stop",
        "Nahi chahiye, refund do",
        "Fraud lag raha hai, block karo",
        "No longer interested. Cancel everything",
    ],
    "UNCLEAR": [
        "Who is this?",
        "Samajh nahi aaya",
        "Wrong number hai",
        "Baad mein baat karte hain",
        "?",
    ],
}


def _simulate_customer_reply(rng: random.Random, promise_status: str) -> str:
    """Pick a random simulated reply matching the desired intent status."""
    return rng.choice(SIMULATED_REPLIES[promise_status])


def run_system_pipeline(
    transactions: List[Dict[str, Any]],
    seed: int = 42,
    log_path: str = "logs/audit_trail.jsonl",
    escalation_log_path: str = "logs/escalation_queue.jsonl",
    live_llm_calls: int = 5,
) -> List[Dict[str, Any]]:
    """Execute the full AutoPey-Rescue intelligence pipeline on transactions.

    Args:
        transactions: List of transaction dictionaries.
        seed: Random seed for deterministic simulation.
        log_path: Filepath for audit trail.
        escalation_log_path: Filepath for escalation queue.
        live_llm_calls: Number of sample records to draft via live LLM API (rest use smart fallback).

    Returns:
        List of systemic outcome dictionaries per transaction.
    """
    rng = random.Random(seed)
    clear_audit_trail(log_path)
    clear_escalation_queue(escalation_log_path)

    outcomes: List[Dict[str, Any]] = []
    nudges_sent_count = 0
    escalation_counts = {"DECLINED_STOP": 0, "PROMISE_BROKEN": 0, "RETRY_SCHEDULED": 0, "HUMAN_REVIEW": 0}

    for txn in transactions:
        txn_id = txn["transaction_id"]
        amount = txn.get("amount_inr", 0)
        failure_code = txn.get("failure_code", "UNKNOWN")

        # Step 1: Deterministic Diagnosis
        root_cause = diagnose(txn)

        # Step 2: Policy Engine
        policy_decision = decide_action(txn, root_cause)

        # Track contact history for this transaction
        contact_history: List[Dict[str, Any]] = []

        recovered = False
        attempts_made = 0
        contacts_sent = 0
        days_to_recovery = None
        last_outreach_msg = None
        final_guardrail_result = {"allowed": False, "reason": "not evaluated"}
        promise_to_pay_status = None
        escalation_path = None

        max_allowed_attempts = policy_decision["max_retries"]

        # If policy allows at least 1 attempt/contact or terminal stop
        if max_allowed_attempts == 0 or policy_decision["action"] == "STOP_AND_FLAG":
            # Terminal stop check
            guardrail_res = is_action_allowed(txn, policy_decision, contact_history)
            final_guardrail_result = guardrail_res
            log_decision(
                transaction=txn,
                root_cause=root_cause,
                policy_decision=policy_decision,
                guardrail_result=guardrail_res,
                outreach_message=None,
                outcome={"recovered": False, "attempts": 0, "contacts": 0},
                log_path=log_path,
            )
        else:
            # Simulate attempt loop up to policy limits
            for attempt_idx in range(1, max_allowed_attempts + 1):
                guardrail_res = is_action_allowed(txn, policy_decision, contact_history)
                final_guardrail_result = guardrail_res

                if not guardrail_res["allowed"]:
                    # Guardrail blocked this attempt
                    log_decision(
                        transaction=txn,
                        root_cause=root_cause,
                        policy_decision=policy_decision,
                        guardrail_result=guardrail_res,
                        outreach_message=None,
                        outcome={"recovered": recovered, "attempts": attempts_made, "contacts": contacts_sent},
                        log_path=log_path,
                    )
                    break

                attempts_made += 1

                # Outreach message drafting (for balance nudges and expired reauth links)
                msg = None
                if policy_decision["action"] in ["HOLD_AND_NUDGE", "REAUTH_LINK"]:
                    if check_global_cap(nudges_sent_count, cap=200):
                        # Use live LLM for sample records, fast contextual fallback for batch throughput
                        if live_llm_calls is not None and nudges_sent_count < live_llm_calls:
                            msg = draft_nudge(txn)
                        else:
                            msg = _fallback_draft_nudge(txn)
                        nudges_sent_count += 1
                        contacts_sent += 1
                        last_outreach_msg = msg

                        # -------------------------------------------------------
                        # Promise-to-Pay Simulation Loop
                        # On first nudge, simulate whether customer replies
                        # -------------------------------------------------------
                        if attempt_idx == 1 and rng.random() < PROMISE_REPLY_RATE:
                            # Choose a reply status weighted by distribution
                            statuses = list(PROMISE_STATUS_DIST.keys())
                            weights = list(PROMISE_STATUS_DIST.values())
                            chosen_status = rng.choices(statuses, weights=weights, k=1)[0]
                            simulated_reply = _simulate_customer_reply(rng, chosen_status)

                            # Parse intent (uses LLM for initial sample, fallback otherwise)
                            if live_llm_calls is not None and nudges_sent_count <= live_llm_calls:
                                promise_result = parse_promise_to_pay(simulated_reply)
                            else:
                                promise_result = _fallback_parse_promise(simulated_reply)
                            promise_to_pay_status = promise_result.get("status")

                            # Classify escalation path
                            days_since = rng.uniform(0.5, 6.0)  # Simulated days since outreach
                            escalation = classify_escalation(txn, promise_result, days_since_contact=days_since)
                            escalation_path = escalation.get("escalation_path")
                            escalation_counts[escalation_path] = escalation_counts.get(escalation_path, 0) + 1

                            # Log to escalation queue
                            log_escalation(txn, escalation, promise_result, log_path=escalation_log_path)

                            # If customer DECLINED → guardrail should stop further contacts
                            if promise_to_pay_status == "DECLINED":
                                # Record this contact then break — no further retries
                                contact_history.append({
                                    "attempt": attempt_idx,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                    "action": policy_decision["action"]
                                })
                                log_decision(
                                    transaction=txn,
                                    root_cause=root_cause,
                                    policy_decision=policy_decision,
                                    guardrail_result=guardrail_res,
                                    outreach_message=msg,
                                    outcome={
                                        "recovered": False, "attempts": attempts_made,
                                        "contacts": contacts_sent,
                                        "promise_to_pay": promise_to_pay_status,
                                        "escalation_path": escalation_path,
                                    },
                                    log_path=log_path,
                                )
                                break

                # Record contact event in transaction history
                contact_history.append({
                    "attempt": attempt_idx,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": policy_decision["action"]
                })

                # Check recovery probability
                prob = SYSTEM_RECOVERY_PROBABILITIES.get(root_cause, 0.20)

                # Boost recovery probability if customer made a promise
                if promise_to_pay_status == "PROMISED":
                    prob = min(prob * 1.20, 0.95)  # 20% uplift for promised customers

                if rng.random() < prob:
                    recovered = True
                    # Estimate realistic days to recovery
                    if root_cause == "technical":
                        days_to_recovery = round(0.25 * attempt_idx, 2)  # Same-day (~6-12 hrs)
                    elif root_cause == "balance":
                        days_to_recovery = round(2.0 * attempt_idx, 2)   # 2-4 days post salary
                    elif root_cause == "expired":
                        days_to_recovery = round(1.5 * attempt_idx, 2)   # Re-authorization turnaround
                    else:
                        days_to_recovery = float(attempt_idx)

                    log_decision(
                        transaction=txn,
                        root_cause=root_cause,
                        policy_decision=policy_decision,
                        guardrail_result=guardrail_res,
                        outreach_message=msg,
                        outcome={
                            "recovered": True,
                            "attempts": attempts_made,
                            "contacts": contacts_sent,
                            "recovered_amount": amount,
                            "days_to_recovery": days_to_recovery,
                            "promise_to_pay": promise_to_pay_status,
                            "escalation_path": escalation_path,
                        },
                        log_path=log_path,
                    )
                    break
                else:
                    # Attempt failed, log and check if next attempt allowed
                    log_decision(
                        transaction=txn,
                        root_cause=root_cause,
                        policy_decision=policy_decision,
                        guardrail_result=guardrail_res,
                        outreach_message=msg,
                        outcome={
                            "recovered": False,
                            "attempts": attempts_made,
                            "contacts": contacts_sent,
                            "promise_to_pay": promise_to_pay_status,
                            "escalation_path": escalation_path,
                        },
                        log_path=log_path,
                    )

        outcomes.append({
            "transaction_id": txn_id,
            "failure_code": failure_code,
            "root_cause": root_cause,
            "chosen_action": policy_decision["action"],
            "amount_inr": amount,
            "recovered": recovered,
            "recovered_amount_inr": amount if recovered else 0,
            "attempts_made": attempts_made,
            "contacts_sent": contacts_sent,
            "days_to_recovery": days_to_recovery,
            "policy": "AUTOPAY_RESCUE_INTELLIGENT",
            "last_outreach_message": last_outreach_msg,
            "guardrail_status": final_guardrail_result.get("reason"),
            "promise_to_pay_status": promise_to_pay_status,
            "escalation_path": escalation_path,
            "merchant_category": txn.get("merchant_category"),
            "customer_segment": txn.get("customer_segment"),
            "risk_score": txn.get("risk_score"),
        })

    # Print escalation summary to stdout
    print(f"\nEscalation Routing Summary (from {nudges_sent_count} nudged transactions):")
    for path, count in escalation_counts.items():
        if count > 0:
            print(f"  {path}: {count} cases")

    return outcomes


def print_comparison_table(system_metrics: Dict[str, Any], baseline_metrics: Dict[str, Any]) -> None:
    """Print an executive side-by-side comparison table to stdout."""
    print("\n" + "=" * 78)
    print("      AUTOPAY RESCUE vs NAIVE BLIND RETRY -- BATCH RECOVERY COMPARISON")
    print("=" * 78)
    print(f"{'Metric':<36} | {'Naive Baseline':<18} | {'AutoPey Rescue':<18}")
    print("-" * 78)

    rec_rate_b = f"{baseline_metrics['recovery_rate_pct']:.1f}%"
    rec_rate_s = f"{system_metrics['recovery_rate_pct']:.1f}%"
    print(f"{'Recovery Rate (%)':<36} | {rec_rate_b:<18} | {rec_rate_s:<18}")

    rec_inr_b = f"INR {baseline_metrics['total_recovered_inr']:,.2f}"
    rec_inr_s = f"INR {system_metrics['total_recovered_inr']:,.2f}"
    print(f"{'Total Revenue Recovered':<36} | {rec_inr_b:<18} | {rec_inr_s:<18}")

    contacts_b = f"{baseline_metrics['total_contacts']}"
    contacts_s = f"{system_metrics['total_contacts']}"
    print(f"{'Total Customer Contacts':<36} | {contacts_b:<18} | {contacts_s:<18}")

    eff_b = f"INR {baseline_metrics['recovered_per_contact']:,.2f}"
    eff_s = f"INR {system_metrics['recovered_per_contact']:,.2f}"
    print(f"{'Recovered INR per Contact':<36} | {eff_b:<18} | {eff_s:<18}")

    days_b = f"{baseline_metrics['avg_days_to_recovery']:.2f} days"
    days_s = f"{system_metrics['avg_days_to_recovery']:.2f} days"
    print(f"{'Average Days to Recovery':<36} | {days_b:<18} | {days_s:<18}")

    print("=" * 78)

    # Efficiency multiplier
    if baseline_metrics["recovered_per_contact"] > 0:
        multiplier = system_metrics["recovered_per_contact"] / baseline_metrics["recovered_per_contact"]
        print(f">> Recovery Efficiency Advantage: {multiplier:.2f}x higher INR recovered per contact!")
    print("=" * 78 + "\n")


def compute_category_breakdown(outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute recovery metrics broken down by failure code category."""
    from collections import defaultdict
    by_code: Dict[str, List] = defaultdict(list)
    for o in outcomes:
        by_code[o.get("failure_code", "UNKNOWN")].append(o)

    breakdown = {}
    for code, items in by_code.items():
        total = len(items)
        recovered = sum(1 for i in items if i.get("recovered"))
        recovered_inr = sum(i.get("recovered_amount_inr", 0) for i in items)
        total_contacts = sum(i.get("contacts_sent", 0) for i in items)
        breakdown[code] = {
            "total": total,
            "recovered": recovered,
            "recovery_rate_pct": round((recovered / total) * 100, 1) if total > 0 else 0.0,
            "total_recovered_inr": recovered_inr,
            "total_contacts": total_contacts,
            "recovered_per_contact": round(recovered_inr / total_contacts, 2) if total_contacts > 0 else 0.0,
        }
    return breakdown


def main():
    parser = argparse.ArgumentParser(description="Run AutoPey-Rescue batch benchmark.")
    parser.add_argument("--data", type=str, default="data/synthetic_transactions.json", help="Input transaction data path")
    parser.add_argument("--results", type=str, default="data/results.json", help="Output results JSON path")
    parser.add_argument("--audit-log", type=str, default="logs/audit_trail.jsonl", help="Audit log JSONL path")
    parser.add_argument("--escalation-log", type=str, default="logs/escalation_queue.jsonl", help="Escalation queue JSONL path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for simulation reproducibility")
    parser.add_argument("--count", type=int, default=200, help="Number of records to generate if data missing")
    parser.add_argument("--live-llm-calls", type=int, default=5, help="Number of real LLM calls to execute during batch (default: 5)")
    args = parser.parse_args()

    # Load or generate transactions
    if not os.path.exists(args.data):
        print(f"Data file '{args.data}' not found. Generating {args.count} synthetic records...")
        transactions = generate_synthetic_transactions(count=args.count, seed=args.seed)
        save_transactions(transactions, output_path=args.data)
    else:
        with open(args.data, "r", encoding="utf-8") as f:
            transactions = json.load(f)

    print(f"Loaded {len(transactions)} transactions from {args.data}.")
    print("Executing AutoPey-Rescue intelligent pipeline...")
    system_outcomes = run_system_pipeline(
        transactions,
        seed=args.seed,
        log_path=args.audit_log,
        escalation_log_path=args.escalation_log,
        live_llm_calls=args.live_llm_calls,
    )
    system_metrics = compute_metrics(system_outcomes)
    system_category_breakdown = compute_category_breakdown(system_outcomes)

    print("Executing Naive Blind-Retry baseline simulation...")
    baseline_outcomes = run_baseline(transactions, seed=args.seed)
    baseline_metrics = compute_metrics(baseline_outcomes)
    baseline_category_breakdown = compute_category_breakdown(baseline_outcomes)

    # Save results
    results_payload = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transaction_count": len(transactions),
            "seed": args.seed,
        },
        "system": {
            "metrics": system_metrics,
            "outcomes": system_outcomes,
            "category_breakdown": system_category_breakdown,
        },
        "baseline": {
            "metrics": baseline_metrics,
            "outcomes": baseline_outcomes,
            "category_breakdown": baseline_category_breakdown,
        },
    }

    os.makedirs(os.path.dirname(args.results), exist_ok=True)
    with open(args.results, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    print(f"Results successfully saved to {args.results}")
    print_comparison_table(system_metrics, baseline_metrics)


if __name__ == "__main__":
    main()
