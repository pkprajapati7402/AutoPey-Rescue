# Autopay Rescue — Build Instructions (phase by phase)

**How to use this file:** Each phase below has a prompt block you can hand directly to an AI coding agent (Claude Code, or similar). Run phases in order — don't skip ahead. After each phase, check the "Definition of done" before moving on. Where it says "Manual step," that's on you; the agent can't do it.

Repo structure this build assumes:

```
autopay-rescue/
├── README.md
├── PLANNING.md
├── requirements.txt
├── .env.example
├── data/
│   └── synthetic_transactions.json
├── src/
│   ├── data_generator.py
│   ├── diagnosis.py
│   ├── policy.py
│   ├── outreach.py
│   ├── guardrails.py
│   ├── audit.py
│   ├── baseline.py
│   ├── metrics.py
│   └── run_batch.py
├── dashboard/
│   └── app.py
├── logs/
├── tests/
└── docs/
    └── architecture.md
```

---

## Phase 0 — Environment & Repo Setup

**Manual steps (do first, before touching the agent):**
1. Create an empty GitHub repo called `autopay-rescue`, clone it locally.
2. Sign up for an LLM API key (Anthropic or OpenAI) if you don't already have one.
3. Decide: Anthropic or OpenAI. Either works — pick whichever you have a key for.

**Prompt for the agent:**
```
Set up a Python project called "autopay-rescue" in the current directory with this structure:
autopay-rescue/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
├── src/
│   └── __init__.py
├── dashboard/
├── logs/
├── tests/
└── docs/

requirements.txt should include: anthropic (or openai, whichever I specify), python-dotenv,
streamlit, pytest. .gitignore should exclude .env, __pycache__, logs/*.jsonl, data/*.json
(but keep .gitkeep placeholders so the folders exist in git). .env.example should have a
placeholder for the LLM API key, e.g. ANTHROPIC_API_KEY=your_key_here. README.md should have
a one-paragraph project description (I'll expand it later) and a "Setup" section explaining:
clone, pip install -r requirements.txt, copy .env.example to .env and fill in the key.
```

**Definition of done:** Repo exists locally, `pip install -r requirements.txt` runs clean, `.env` (not `.env.example`) holds your real key and is gitignored.

---

## Phase 1 — Synthetic Data Generator

**Prompt for the agent:**
```
Create src/data_generator.py. It should generate a synthetic batch of failed UPI Autopay
mandate transactions and save them to data/synthetic_transactions.json.

Each transaction is a dict with fields:
- transaction_id (e.g. "TXN00001", zero-padded, sequential)
- subscription_id (e.g. "SUB00019")
- customer_id (e.g. "CUST00019")
- customer_name (realistic Indian names, mix of first+last)
- amount_inr (integer, realistic subscription amounts like 199, 299, 499, 999, 1499)
- due_date (ISO date, spread across the last 30 days)
- failure_code: one of "TECH_TIMEOUT", "INSUFFICIENT_BALANCE", "MANDATE_EXPIRED",
  "HARD_DECLINE_OR_CANCELLED"
- attempt_number (starts at 1)
- opted_out (boolean, true for ~5% of records)
- created_at (ISO timestamp)

Distribution across failure_code should roughly mirror real-world UPI Autopay decline
patterns: INSUFFICIENT_BALANCE ~45%, TECH_TIMEOUT ~25%, MANDATE_EXPIRED ~15%,
HARD_DECLINE_OR_CANCELLED ~15%. Generate 200 records by default, configurable via a
--count CLI argument. Make the script runnable directly: `python src/data_generator.py`
writes data/synthetic_transactions.json. Print a summary of the generated distribution
to stdout when it finishes.

Add tests/test_data_generator.py with at least one test that checks the output has the
right number of records and that every failure_code value is valid.
```

**Definition of done:** `python src/data_generator.py` produces `data/synthetic_transactions.json` with ~200 varied, realistic-looking records. `pytest tests/test_data_generator.py` passes.

---

## Phase 2 — Deterministic Diagnosis Engine

**Prompt for the agent:**
```
Create src/diagnosis.py. This module maps a transaction's failure_code to a root_cause
category using a plain lookup table — NOT an LLM call, this must be deterministic and
explainable.

Mapping:
- TECH_TIMEOUT -> "technical"
- INSUFFICIENT_BALANCE -> "balance"
- MANDATE_EXPIRED -> "expired"
- HARD_DECLINE_OR_CANCELLED -> "terminal"

Expose a function diagnose(transaction: dict) -> str that returns the root_cause category.
Raise a clear ValueError if failure_code is unrecognized — don't silently default.

Add tests/test_diagnosis.py covering all four categories plus the unrecognized-code error
case.

Add a short comment block at the top of diagnosis.py explaining WHY this is a rule-based
lookup instead of a model call — this project intentionally uses AI only where it adds
value, not everywhere.
```

**Definition of done:** `diagnose()` correctly classifies all four failure codes; the unrecognized-code case raises instead of guessing; tests pass.

---

## Phase 3 — Intervention Policy Engine

**Prompt for the agent:**
```
Create src/policy.py. This module decides WHAT ACTION to take for a transaction, given
its root_cause category from diagnosis.py.

Policy table:
- "technical" -> action "AUTO_RETRY", max_retries=2, min_gap_hours=4
- "balance" -> action "HOLD_AND_NUDGE", max_retries=2, min_gap_hours=48
- "expired" -> action "REAUTH_LINK", max_retries=1, min_gap_hours=None
- "terminal" -> action "STOP_AND_FLAG", max_retries=0, min_gap_hours=None

Expose a function decide_action(transaction: dict, root_cause: str) -> dict that returns
{"action": ..., "max_retries": ..., "min_gap_hours": ...}. This function should NOT check
guardrails itself (attempt counts, cooldowns, opt-out) — that's guardrails.py's job in
Phase 5. Keep this module focused only on "what is the right kind of action for this root
cause," not "is it currently allowed to happen."

Add tests/test_policy.py covering all four root causes and asserting the correct action
and limits come back.
```

**Definition of done:** `decide_action()` returns the correct action + limits for each root cause. Tests pass. This module has no guardrail logic yet — that's intentional, keep phases separated.

---

## Phase 4 — LLM Outreach & Promise-to-Pay

**Prompt for the agent:**
```
Create src/outreach.py. This is the ONLY module in the project that calls an LLM — use it
deliberately, not everywhere.

Function 1: draft_nudge(transaction: dict) -> str
Calls the LLM API (Anthropic or OpenAI, read the key from the environment via python-dotenv)
to draft a short WhatsApp-style payment reminder in Hinglish (Hindi-English mix, natural
tone, not textbook Hindi). It must reference the customer's first name, the amount_inr, and
the due_date. Tone: polite, low-pressure, not threatening. Keep it under 300 characters.
This message is NEVER actually sent anywhere — it's captured as text and logged. Do not
integrate any real WhatsApp/SMS sending API.

Function 2: parse_promise_to_pay(customer_reply: str) -> dict
Given a simulated customer reply string (for the demo, we'll feed in fake replies like
"haan kal kar dunga" or "no I cancelled this"), use the LLM to classify it into one of:
"PROMISED" (with an extracted promised_date if mentioned, else null), "DECLINED", or
"UNCLEAR". Return {"status": ..., "promised_date": ...}. This should be defensive: if the
LLM response can't be parsed as expected, default to "UNCLEAR" rather than crashing.

Add a fallback mode: if no API key is present in the environment, both functions should
return a clearly-labeled placeholder response instead of crashing, so the rest of the
pipeline can still be tested without burning API credits.

Add tests/test_outreach.py that tests the fallback (no-API-key) path — don't burn real API
calls in automated tests.
```

**Manual step:** Make sure your `.env` has a real key before you run this against the actual batch — the fallback path is for testing only, not for your final numbers.

**Definition of done:** With a real key set, `draft_nudge()` produces a natural Hinglish message under 300 characters; `parse_promise_to_pay()` correctly classifies a few manually-tested example replies. Without a key, both functions degrade gracefully instead of crashing.

---

## Phase 5 — Guardrails & Stopping Rules

**Prompt for the agent:**
```
Create src/guardrails.py. This is the safety layer that decides whether an action from
policy.py is actually ALLOWED to happen right now, given the transaction's history.

Function: is_action_allowed(transaction: dict, policy_decision: dict, contact_history: list) -> dict
Returns {"allowed": bool, "reason": str}.

Rules to enforce, in this order, first match wins:
1. If transaction["opted_out"] is True -> not allowed, reason "customer opted out"
2. If policy_decision["action"] == "STOP_AND_FLAG" -> not allowed, reason "terminal category, no contact permitted"
3. If len(contact_history) >= policy_decision["max_retries"] -> not allowed, reason "max retries reached"
4. If contact_history is non-empty and the most recent contact was less than
   policy_decision["min_gap_hours"] ago -> not allowed, reason "cooldown period active"
5. Otherwise -> allowed, reason "within policy limits"

Also add a global guardrail function: check_global_cap(nudges_sent_today: int, cap: int = 50) -> bool
that returns False once a batch run has sent more than `cap` nudges — this exists so a bug
elsewhere can't turn this into something that looks like it's spamming an entire customer
base, even in simulation.

Add tests/test_guardrails.py covering each of the 5 rules individually, plus the global cap.
```

**Definition of done:** Every guardrail rule has a passing test that proves it actually blocks the action it's supposed to block — not just that the function runs.

---

## Phase 6 — Audit Trail

**Prompt for the agent:**
```
Create src/audit.py. This logs one structured entry per decision made during a batch run,
to logs/audit_trail.jsonl (JSON Lines format, one JSON object per line, append-only).

Function: log_decision(transaction, root_cause, policy_decision, guardrail_result, outreach_result=None)
Each logged entry should include: timestamp, transaction_id, failure_code, root_cause,
chosen_action, was_allowed (bool), block_reason (if not allowed), outreach_message (if any),
and outcome (leave as null here — outcome gets filled in later during the batch run in
Phase 7 when we know if the retry succeeded).

Also add a function load_audit_trail() -> list that reads the whole file back as a list of
dicts, for use by the dashboard later.

This file is the single most important artifact in the whole project for the demo — keep
the schema clean and consistent, this is what a reviewer will actually open and read.
```

**Definition of done:** Running any decision through this module appends a readable, well-formed line to `logs/audit_trail.jsonl`. `load_audit_trail()` correctly reads it back.

---

## Phase 7 — Baseline & Metrics

**Prompt for the agent:**
```
Create src/baseline.py and src/metrics.py, plus src/run_batch.py that ties the whole
pipeline together.

baseline.py: implement run_baseline(transactions: list) -> list of outcomes, simulating
a naive policy — retry every transaction every 24 hours, up to 3 attempts, same generic
message every time, no root-cause logic, no stop conditions except running out of
attempts. For simulation purposes, define a simple recovery probability per failure_code
(you decide reasonable values, e.g. TECH_TIMEOUT recovers ~70% of the time on any retry,
INSUFFICIENT_BALANCE ~30% per blind retry, MANDATE_EXPIRED ~5% per blind retry,
HARD_DECLINE_OR_CANCELLED ~0%) and use it to probabilistically simulate whether each
retry attempt succeeds. Use a fixed random seed so results are reproducible.

run_batch.py: for the SYSTEM (not baseline), run every transaction through
diagnosis.py -> policy.py -> guardrails.py -> outreach.py (only when guardrails allow it)
-> audit.py, simulating outcomes with recovery probabilities that are HIGHER than the
baseline's blind-retry probability for the matching failure_code where the action taken
is the appropriate one (this is the honest justification for why the smarter policy
should outperform blind retry) — again using a fixed seed. Save results to
data/results.json with two top-level sections: "system" and "baseline".

metrics.py: implement compute_metrics(outcomes: list) -> dict returning recovery_rate_pct,
total_recovered_inr, total_contacts, recovered_per_contact, avg_days_to_recovery. Use this
to compute metrics for both system and baseline outcomes and print a clean side-by-side
comparison table to stdout when run_batch.py finishes.

Add tests/test_metrics.py testing compute_metrics on a small hand-built list of outcomes
with a known expected result.
```

**Definition of done:** `python src/run_batch.py` runs the full pipeline end to end on the synthetic batch, writes `data/results.json`, and prints a system-vs-baseline comparison table. The system's recovered-per-contact ratio should beat the baseline's — if it doesn't, that's a real signal to go look at your recovery probabilities honestly, not to fudge the numbers.

---

## Phase 8 — Demo Dashboard

**Prompt for the agent:**
```
Create dashboard/app.py using Streamlit. It should:
1. Load data/results.json and display the system-vs-baseline metrics as a comparison
   table and a bar chart (recovery rate, ₹ recovered, total contacts, recovered-per-contact).
2. Load logs/audit_trail.jsonl via audit.load_audit_trail() and display it as a
   searchable/filterable table (filter by failure_code and by whether the action was
   allowed).
3. Add a "Spotlight" section that lets me pick one transaction_id and see its full story:
   what failure it had, what root cause was diagnosed, what action was chosen, whether it
   was allowed, the outreach message if any, and the outcome — this is for walking through
   one example live in the pitch video.

Keep the styling minimal and functional — this is for a 5-minute demo video, not a
production UI. Make sure `streamlit run dashboard/app.py` works with no errors.
```

**Definition of done:** `streamlit run dashboard/app.py` opens a working dashboard showing real numbers from your actual batch run, and you can pull up any single transaction's full story on demand.

---

## Phase 9 — Documentation & Repo Polish

**Prompt for the agent:**
```
Update README.md to be a complete, honest project overview: what the project does, the
architecture diagram (copy from PLANNING.md), how to set up and run it end to end
(data generation -> batch run -> dashboard), what's simulated vs real (be explicit that
outreach messages are logged, not sent, and that the data is synthetic), and the final
system-vs-baseline numbers from your actual run.

Create docs/architecture.md with the module-by-module breakdown: what each file in src/
does and why it exists, written so a reviewer skimming the repo for 5 minutes understands
the design without reading all the code.

Do not write anything in the README that isn't true of what's actually in the repo —
no aspirational features, no claims about integrations that don't exist.
```

**Definition of done:** A reviewer with no context could clone the repo, follow the README, and reproduce your results.

---

## Phase 10 — Test Run, Edge Cases & the "What Broke" Story

**This phase is manual, not a prompt for the agent.** Run the full pipeline yourself, end to end, at least twice. While you do:

1. Watch for something that genuinely doesn't work the way you expected — a misclassified edge case, a guardrail that blocks something it shouldn't (or doesn't block something it should), an outreach message that comes out in the wrong tone, a metric that looks suspiciously good or bad.
2. Fix it, and write down, in a sentence or two, what broke, why, and what you changed. That's your answer for the "Build Challenges & Technical Obstacles" field on the application — don't invent one, use the real one.
3. Re-run the batch after the fix and confirm the numbers in `data/results.json` are the ones you'll actually report in the form.

**Definition of done:** You have one true story of something breaking and getting fixed, and the numbers in your README/dashboard match the numbers you're about to type into the application form.

---

## Phase 11 (Optional / stretch — only if Day 3 arrives early)

Real Razorpay test-mode integration: sign up for Razorpay test-mode API keys, and swap the synthetic data generator for actual test-mode Subscription/Payment Link failure events where possible. This is a nice-to-have, not a requirement — a clean, honestly-measured synthetic version beats a half-finished real integration. Don't start this until everything above is done and working.
