"""Synthetic Data Generator for Failed UPI Autopay Mandate Transactions.

Generates realistic synthetic batches of UPI Autopay failure transactions
mirroring real-world distribution patterns across failure codes, subscription
amounts, customer demographics, and opt-out statuses.
"""

import argparse
from collections import Counter
from datetime import datetime, timedelta
import json
import os
import random
from typing import List, Dict, Any

# Target failure code distributions mirroring real-world Indian UPI Autopay metrics
FAILURE_CODES = [
    "INSUFFICIENT_BALANCE",
    "TECH_TIMEOUT",
    "MANDATE_EXPIRED",
    "HARD_DECLINE_OR_CANCELLED",
]
FAILURE_WEIGHTS = [0.45, 0.25, 0.15, 0.15]

# Common subscription plan tiers in India (INR)
SUBSCRIPTION_AMOUNTS = [199, 299, 499, 699, 999, 1499, 1999]
AMOUNT_WEIGHTS = [0.25, 0.25, 0.20, 0.10, 0.10, 0.05, 0.05]

# Realistic Indian customer first and last names for diverse synthetic generation
FIRST_NAMES = [
    "Aarav", "Aditi", "Amit", "Ananya", "Deepak", "Divya", "Gaurav", "Isha",
    "Karan", "Kavita", "Manish", "Neha", "Nikhil", "Pooja", "Pranav", "Priya",
    "Rahul", "Rakesh", "Riya", "Rohan", "Rohit", "Sakshi", "Sanjay", "Shreya",
    "Siddharth", "Sneha", "Sunil", "Tanvi", "Varun", "Vikram"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Gupta", "Singh", "Kumar", "Iyer",
    "Reddy", "Nair", "Deshmukh", "Chopra", "Joshi", "Bhat", "Kulkarni",
    "Malhotra", "Saxena", "Choudhury", "Das", "Rao"
]


def generate_synthetic_transactions(
    count: int = 200,
    seed: int = 42
) -> List[Dict[str, Any]]:
    """Generate a reproducible synthetic batch of failed UPI Autopay transactions.

    Args:
        count: Number of failed transaction records to generate.
        seed: Random seed for deterministic reproducibility.

    Returns:
        List of transaction dictionaries.
    """
    random.seed(seed)
    transactions: List[Dict[str, Any]] = []
    base_date = datetime(2026, 8, 30, 10, 0, 0)

    for i in range(1, count + 1):
        txn_id = f"TXN{i:05d}"
        sub_id = f"SUB{i:05d}"
        cust_id = f"CUST{i:05d}"

        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        customer_name = f"{first} {last}"

        amount = random.choices(SUBSCRIPTION_AMOUNTS, weights=AMOUNT_WEIGHTS, k=1)[0]
        failure_code = random.choices(FAILURE_CODES, weights=FAILURE_WEIGHTS, k=1)[0]

        # Due date spread across the last 30 days
        days_ago = random.randint(1, 30)
        hour_offset = random.randint(0, 23)
        minute_offset = random.randint(0, 59)
        due_datetime = base_date - timedelta(
            days=days_ago,
            hours=hour_offset,
            minutes=minute_offset
        )
        due_date_str = due_datetime.strftime("%Y-%m-%d")
        created_at_str = due_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")

        # ~5% opted out
        opted_out = random.random() < 0.05

        record = {
            "transaction_id": txn_id,
            "subscription_id": sub_id,
            "customer_id": cust_id,
            "customer_name": customer_name,
            "amount_inr": amount,
            "due_date": due_date_str,
            "failure_code": failure_code,
            "attempt_number": 1,
            "opted_out": opted_out,
            "created_at": created_at_str,
        }
        transactions.append(record)

    return transactions


def save_transactions(
    transactions: List[Dict[str, Any]],
    output_path: str = "data/synthetic_transactions.json"
) -> None:
    """Save transaction records to a JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(transactions, f, indent=2)


def print_distribution_summary(transactions: List[Dict[str, Any]]) -> None:
    """Print a clean summary of the generated distribution to stdout."""
    total = len(transactions)
    counts = Counter(t["failure_code"] for t in transactions)
    opt_outs = sum(1 for t in transactions if t["opted_out"])
    total_amount = sum(t["amount_inr"] for t in transactions)

    print("=" * 60)
    print(f"  SYNTHETIC DATA GENERATION SUMMARY (Total: {total} records)")
    print("=" * 60)
    print(f"Total Portfolio Value At Risk: INR {total_amount:,.2f}")
    print(f"Customer Opt-Outs: {opt_outs} ({(opt_outs/total)*100:.1f}%)")
    print("-" * 60)
    print("Failure Code Breakdown:")
    for code in FAILURE_CODES:
        c = counts.get(code, 0)
        pct = (c / total) * 100 if total > 0 else 0
        print(f"  - {code:<28} : {c:>4} records ({pct:>5.1f}%)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic failed UPI Autopay mandate transactions."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=200,
        help="Number of records to generate (default: 200)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/synthetic_transactions.json",
        help="Output JSON file path"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)"
    )
    args = parser.parse_args()

    records = generate_synthetic_transactions(count=args.count, seed=args.seed)
    save_transactions(records, output_path=args.output)
    print(f"Successfully wrote {len(records)} records to {args.output}")
    print_distribution_summary(records)


if __name__ == "__main__":
    main()
