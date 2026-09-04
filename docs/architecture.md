# Architecture & System Design — AutoPey-Rescue

**Track:** 03 — AI Revenue Recovery  
**Platform Pitch:** An intelligent agent that diagnoses *why* a UPI Autopay / e-mandate payment failed and executes bounded, root-cause-specific actions with compliant escalation, promise-to-pay tracking, and a measurable audit trail.

---

## 1. System Architecture Diagram

```
                    ┌─────────────────────────┐
                    │ Synthetic Data Generator│ (src/data_generator.py)
                    └───────────┬─────────────┘
                                │ 200 failed mandate records with risk_score,
                                │ customer_segment, merchant_category
                                ▼
                    ┌─────────────────────────┐
                    │ Deterministic Diagnosis │ (src/diagnosis.py) — NO LLM
                    └───────────┬─────────────┘
                                │ root_cause: [technical, balance, expired, terminal]
                                ▼
                    ┌─────────────────────────┐
                    │  Intervention Policy    │ (src/policy.py) — Rule table
                    └───────────┬─────────────┘
                                │ action: [AUTO_RETRY, HOLD_AND_NUDGE, REAUTH_LINK, STOP_AND_FLAG]
                  ┌─────────────┴─────────────┐
                  ▼                           ▼
        ┌──────────────────┐        ┌───────────────────────┐
        │  Safety Guardrail │        │  Gemini LLM Outreach  │ (src/outreach.py)
        │ (src/guardrails.py)│       │  Hinglish nudge       │ ← ONLY LLM component
        └─────────┬────────┘        │  Promise-to-Pay parse │
                  │                 └──────────┬────────────┘
                  │                            │
                  │                 ┌──────────▼────────────┐
                  │                 │  Escalation Engine    │ (src/escalation.py) NEW
                  │                 │  DECLINED_STOP        │ ← immediate permanent stop
                  │                 │  PROMISE_BROKEN       │ ← human escalation
                  │                 │  RETRY_SCHEDULED      │ ← hold for promised date
                  │                 │  HUMAN_REVIEW         │ ← ambiguous → support team
                  │                 └──────────┬────────────┘
                  └─────────────┬──────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │   Append-Only Audit     │ (src/audit.py) → logs/audit_trail.jsonl
                    │   Escalation Queue      │ (src/escalation.py) → logs/escalation_queue.jsonl
                    └───────────┬─────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │   Metrics & Baseline    │ (src/baseline.py, src/metrics.py)
                    └───────────┬─────────────┘ → data/results.json
                                ▼
                    ┌─────────────────────────┐
                    │ Streamlit Demo Dashboard│ (dashboard/app.py)
                    └─────────────────────────┘
```

---

## 2. Module Breakdown

### `src/data_generator.py`
- **Purpose**: Generates realistic synthetic batches of failed UPI Autopay transactions.
- **Key Parameters**:
  - `INSUFFICIENT_BALANCE` (~45%), `TECH_TIMEOUT` (~25%), `MANDATE_EXPIRED` (~15%), `HARD_DECLINE_OR_CANCELLED` (~15%)
  - Subscription tiers: ₹199, ₹299, ₹499, ₹699, ₹999, ₹1,499, ₹1,999
  - ~5% pre-existing customer opt-outs
  - **NEW Fields**: `merchant_category`, `customer_segment` (High Value/Mid Tier/Budget/At Risk/Churning), `previous_failure_count`, `risk_score` (computed composite 0.0–1.0)

---

### `src/diagnosis.py`
- **Purpose**: Deterministically maps raw bank/PSP failure codes to standard root causes.
- **Core Principle**: *Zero LLM in financial rules.* Standardized bank error codes are deterministic; using an LLM here introduces latency, cost, and unpredictability.
- **Mapping**:
  - `TECH_TIMEOUT` → `"technical"`
  - `INSUFFICIENT_BALANCE` → `"balance"`
  - `MANDATE_EXPIRED` → `"expired"`
  - `HARD_DECLINE_OR_CANCELLED` → `"terminal"`
- **Error Handling**: Raises `ValueError` on unrecognized codes — does not silently default.

---

### `src/policy.py`
- **Purpose**: Decides the strategic intervention parameters for each root cause.
- **Policies**:

| Root Cause | Action | Max Retries | Min Gap |
|---|---|---|---|
| `technical` | `AUTO_RETRY` | 2 | 4 hours |
| `balance` | `HOLD_AND_NUDGE` | 2 | 48 hours |
| `expired` | `REAUTH_LINK` | 1 | None |
| `terminal` | `STOP_AND_FLAG` | 0 | None |

- **Boundary**: This module only answers "what action is right for this root cause?" — it does NOT enforce runtime constraints (guardrails do that).

---

### `src/outreach.py` *(Only LLM-touching module)*
- **Purpose**: Generates natural, empathetic Hinglish WhatsApp payment reminders (<300 chars) and classifies customer reply intents.
- **Model Support**: Google Gemini 2.0 Flash (`google-genai` SDK), OpenAI GPT-4o Mini, Anthropic Claude 3 Haiku, Offline Heuristic Fallback
- **`draft_nudge()`**: Context-aware per failure code. `INSUFFICIENT_BALANCE` gets salary-aligned messaging; `MANDATE_EXPIRED` gets renewal request; `TECH_TIMEOUT` gets reassurance.
- **`parse_promise_to_pay()`**: Classifies free-form Hinglish/English replies → `PROMISED` (with date extraction) | `DECLINED` | `UNCLEAR`.
- **Resilience**: If no API key, degrades to smart per-failure-code template variants (not a single generic message).

---

### `src/guardrails.py`
- **Purpose**: Dynamic runtime safety enforcement. Every potential action passes through this before execution.
- **Strict First-Match-Wins Hierarchy**:
  1. `opted_out == True` → BLOCKED, reason "customer opted out"
  2. `action == STOP_AND_FLAG` → BLOCKED, reason "terminal category"
  3. `len(contact_history) >= max_retries` → BLOCKED, reason "max retries reached"
  4. `elapsed < min_gap_hours` → BLOCKED, reason "cooldown period active"
  5. Otherwise → ALLOWED
- **Global Batch Cap**: `check_global_cap()` prevents runaway automated outreach across all run modes.

---

### `src/escalation.py` *(NEW)*
- **Purpose**: The compliance escalation workflow. This is what the Razorpay evaluation bar specifically asks for: *"compliant escalation, stopping rules, and an audit trail."*
- **`classify_escalation()`**: Takes parsed promise intent → routes to one of:
  - `DECLINED_STOP` (HIGH priority) — Customer terminated. Immediate permanent stop. CRM update.
  - `PROMISE_BROKEN` (HIGH priority) — Promise date passed without payment. Human escalation.
  - `RETRY_SCHEDULED` (LOW/MEDIUM) — Promise made, not yet due. Hold automated retries.
  - `HUMAN_REVIEW` (MEDIUM) — Ambiguous response. Route to support team.
- **`log_escalation()`**: Appends to `logs/escalation_queue.jsonl`.
- **`get_escalation_summary()`**: Aggregates counts by path and priority for dashboard.

---

### `src/audit.py`
- **Purpose**: Writes immutable JSON Lines entries to `logs/audit_trail.jsonl`.
- **Schema per entry**: `timestamp`, `transaction_id`, `subscription_id`, `customer_id`, `customer_name`, `amount_inr`, `due_date`, `failure_code`, `root_cause`, `chosen_action`, `was_allowed`, `block_reason`, `outreach_message`, `outcome`.
- **Append-only**: Never overwrites, always appends. `clear_audit_trail()` is only called at the start of a fresh batch run.

---

### `src/baseline.py`
- **Purpose**: Models the legacy naive blind-retry approach for benchmarking comparison.
- **Behavior**: Every failed transaction is retried every 24 hours, up to 3 times, with a generic message, no root-cause logic, no stop conditions.
- **Recovery Probabilities** (modeled from known failure semantics — assumptions, not measured data):
  - `TECH_TIMEOUT`: 70% (transient glitches resolve on retry)
  - `INSUFFICIENT_BALANCE`: 30% (blind next-day retry rarely catches funds)
  - `MANDATE_EXPIRED`: 5% (retrying expired mandate almost always fails)
  - `HARD_DECLINE_OR_CANCELLED`: 0% (terminal — never recovers)

---

### `src/metrics.py`
- **Purpose**: Computes standardized KPIs from outcome lists.
- **Metrics**:
  - `recovery_rate_pct` — % of mandates that recovered
  - `total_recovered_inr` — Total rupees recovered
  - `total_contacts` — Total customer touches dispatched
  - `recovered_per_contact` — INR recovered per contact (core efficiency ratio)
  - `avg_days_to_recovery` — Mean time from failure to recovery

---

### `src/run_batch.py`
- **Purpose**: Orchestrates the complete end-to-end pipeline.
- **NEW in v2**: Promise-to-pay intent processing loop — 20% of nudged customers reply (PROMISED 55%, DECLINED 25%, UNCLEAR 20%). DECLINED customers get immediate contact stop. PROMISED customers get 20% recovery probability uplift. All escalations are classified and logged.
- **Output**: `data/results.json` with system metrics, baseline metrics, per-category breakdowns, and full outcome arrays.

---

### `dashboard/app.py`
- **Purpose**: Interactive Streamlit web application.
- **Tabs**:
  1. **Executive Benchmark** — Hero KPI scorecards, recovery funnel visualization, 3 comparison charts, full benchmark matrix
  2. **Category Deep Dive** — Per-failure-code grouped bar charts, customer segment analysis
  3. **Escalation Queue** — Priority-colored escalation cards, path distribution pie chart, filterable table
  4. **Audit Trail** — Searchable, filterable full audit log
  5. **Transaction Spotlight** — Full pipeline trace for any individual mandate (pitch video tool)
  6. **Live Pipeline Tester** — Real-time diagnosis → policy → guardrail → Hinglish nudge generation and promise-to-pay intent classification
