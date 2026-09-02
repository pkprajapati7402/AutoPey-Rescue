"""Batch Execution Pipeline for AutoPey-Rescue.

Orchestrates the complete recovery loop across all synthetic transactions:
1. Deterministic Root-Cause Diagnosis
2. Intervention Policy Selection
3. Safety Guardrails & Stopping Rules Enforcement
4. LLM Outreach Generation & Intent Parsing (Google Gemini / Fallback)
5. Structured Append-Only Audit Trail Logging
6. Comparative Simulation Benchmarking Against Naive Blind Retry Baseline
7. Metric Calculations & Export to data/results.json
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
from src.outreach import draft_nudge
from src.audit import log_decision, clear_audit_trail
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


def run_system_pipeline(
    transactions: List[Dict[str, Any]],
    seed: int = 42,
    log_path: str = "logs/audit_trail.jsonl"
) -> List[Dict[str, Any]]:
    """Execute the full AutoPey-Rescue intelligence pipeline on transactions.

    Args:
        transactions: List of transaction dictionaries.
        seed: Random seed for deterministic simulation.
        log_path: Filepath for audit trail.

    Returns:
        List of systemic outcome dictionaries per transaction.
    """
    rng = random.Random(seed)
    clear_audit_trail(log_path)

    outcomes: List[Dict[str, Any]] = []
    nudges_sent_count = 0

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
                    if check_global_cap(nudges_sent_count, cap=150):
                        msg = draft_nudge(txn)
                        nudges_sent_count += 1
                        contacts_sent += 1
                        last_outreach_msg = msg

                # Record contact event in transaction history
                contact_history.append({
                    "attempt": attempt_idx,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": policy_decision["action"]
                })

                # Check recovery probability
                prob = SYSTEM_RECOVERY_PROBABILITIES.get(root_cause, 0.20)
                if rng.random() < prob:
                    recovered = True
                    # Estimate realistic days to recovery
                    if root_cause == "technical":
                        days_to_recovery = round(0.25 * attempt_idx, 2)  # Same-day recovery (~6-12 hrs)
                    elif root_cause == "balance":
                        days_to_recovery = round(2.0 * attempt_idx, 2)   # 2-4 days post salary alignment
                    elif root_cause == "expired":
                        days_to_recovery = round(1.5 * attempt_idx, 2)   # Re-authorization link turnaround
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
                            "days_to_recovery": days_to_recovery
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
                        outcome={"recovered": False, "attempts": attempts_made, "contacts": contacts_sent},
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
        })

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


def main():
    parser = argparse.ArgumentParser(description="Run AutoPey-Rescue batch benchmark.")
    parser.add_argument("--data", type=str, default="data/synthetic_transactions.json", help="Input transaction data path")
    parser.add_argument("--results", type=str, default="data/results.json", help="Output results JSON path")
    parser.add_argument("--audit-log", type=str, default="logs/audit_trail.jsonl", help="Audit log JSONL path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for simulation reproducibility")
    parser.add_argument("--generate-if-missing", action="store_true", default=True, help="Generate dataset if not found")
    args = parser.parse_args()

    # Load or generate transactions
    if not os.path.exists(args.data):
        print(f"Data file '{args.data}' not found. Generating 200 synthetic records...")
        transactions = generate_synthetic_transactions(count=200, seed=args.seed)
        save_transactions(transactions, output_path=args.data)
    else:
        with open(args.data, "r", encoding="utf-8") as f:
            transactions = json.load(f)

    print(f"Loaded {len(transactions)} transactions from {args.data}.")
    print("Executing AutoPey-Rescue intelligent pipeline...")
    system_outcomes = run_system_pipeline(transactions, seed=args.seed, log_path=args.audit_log)
    system_metrics = compute_metrics(system_outcomes)

    print("Executing Naive Blind-Retry baseline simulation...")
    baseline_outcomes = run_baseline(transactions, seed=args.seed)
    baseline_metrics = compute_metrics(baseline_outcomes)

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
        },
        "baseline": {
            "metrics": baseline_metrics,
            "outcomes": baseline_outcomes,
        },
    }

    os.makedirs(os.path.dirname(args.results), exist_ok=True)
    with open(args.results, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    print(f"Results successfully saved to {args.results}")
    print_comparison_table(system_metrics, baseline_metrics)


if __name__ == "__main__":
    main()
