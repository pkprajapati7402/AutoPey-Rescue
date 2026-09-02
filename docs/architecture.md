# Architecture & System Design — AutoPey-Rescue

**Track:** 03 — AI Revenue Recovery  
**Platform Pitch:** An intelligent agent that diagnoses *why* a UPI Autopay / e-mandate payment failed and executes bounded, root-cause-specific actions instead of naive blind retries.

---

## 1. System Architecture Diagram

```
                    ┌─────────────────────────┐
                    │ Synthetic Data Generator│ (src/data_generator.py)
                    └───────────┬─────────────┘
                                │ failed_transactions.json
                                ▼
                    ┌─────────────────────────┐
                    │ Deterministic Diagnosis │ (src/diagnosis.py)
                    └───────────┬─────────────┘
                                │ root_cause: [technical, balance, expired, terminal]
                                ▼
                    ┌─────────────────────────┐
                    │  Intervention Policy    │ (src/policy.py)
                    └───────────┬─────────────┘
                                │ action: [AUTO_RETRY, HOLD_AND_NUDGE, REAUTH_LINK, STOP_AND_FLAG]
                  ┌─────────────┴─────────────┐
                  ▼                           ▼
        ┌──────────────────┐        ┌───────────────────┐
        │  Retry Scheduler │        │  Gemini Outreach  │ (src/outreach.py)
        │ (Short Cooldown) │        │ & Promise-to-Pay  │ Hinglish copy + intent
        └─────────┬────────┘        └─────────┬─────────┘
                  │                           │
                  └─────────────┬─────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │    Safety Guardrails    │ (src/guardrails.py)
                    │ (Caps, cooldown, stops) │
                    └───────────┬─────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │   Append-Only Audit     │ (src/audit.py) → logs/audit_trail.jsonl
                    └───────────┬─────────────┘
                                ▼
                    ┌─────────────────────────┐
                    │   Metrics & Baseline    │ (src/baseline.py, src/metrics.py, src/run_batch.py)
                    └───────────┬─────────────┘ → data/results.json
                                ▼
                    ┌─────────────────────────┐
                    │ Streamlit Demo Dashboard│ (dashboard/app.py)
                    └─────────────────────────┘
```

---

## 2. Module Breakdown

### `src/data_generator.py`
- **Purpose**: Generates realistic synthetic batches of failed UPI Autopay transactions mirroring actual Indian recurring payment distributions.
- **Key Parameters**:
  - `INSUFFICIENT_BALANCE` (~45%)
  - `TECH_TIMEOUT` (~25%)
  - `MANDATE_EXPIRED` (~15%)
  - `HARD_DECLINE_OR_CANCELLED` (~15%)
  - Subscription tiers: ₹199, ₹299, ₹499, ₹699, ₹999, ₹1,499, ₹1,999.
  - ~5% pre-existing customer opt-outs.

### `src/diagnosis.py`
- **Purpose**: Deterministically maps raw bank/PSP failure codes to standard root causes.
- **Core Principle**: *Zero LLM Hallucinations in Financial Rules*. Standardized bank error codes are deterministic; using an LLM here would introduce unnecessary latency, cost, and unpredictability.
- **Mapping**:
  - `TECH_TIMEOUT` → `"technical"`
  - `INSUFFICIENT_BALANCE` → `"balance"`
  - `MANDATE_EXPIRED` → `"expired"`
  - `HARD_DECLINE_OR_CANCELLED` → `"terminal"`

### `src/policy.py`
- **Purpose**: Decides the strategic intervention parameters for each root cause category.
- **Policies**:
  - `technical`: `AUTO_RETRY` (Max 2 retries, 4h cooldown).
  - `balance`: `HOLD_AND_NUDGE` (Max 2 retries, 48h cooldown + salary cycle alignment).
  - `expired`: `REAUTH_LINK` (Max 1 re-auth dispatch, no automated blind debits).
  - `terminal`: `STOP_AND_FLAG` (0 retries, immediate hard stop).

### `src/outreach.py`
- **Purpose**: Generates natural, empathetic Hinglish WhatsApp payment reminders (<300 chars) and classifies customer reply intents.
- **Model Support**:
  - **Google Gemini API** (`GEMINI_API_KEY` / `GOOGLE_API_KEY` - Free tier / production ready)
  - OpenAI (`OPENAI_API_KEY`)
  - Anthropic (`ANTHROPIC_API_KEY`)
  - Offline Heuristic Fallback (for 100% resilient testing and zero-cost local execution).
- **Intent Parsing**: Classifies simulated customer replies into `PROMISED` (extracting promise date), `DECLINED`, or `UNCLEAR`.

### `src/guardrails.py`
- **Purpose**: Dynamic runtime safety enforcement before any action or customer contact.
- **Strict Hierarchy (First Match Wins)**:
  1. Customer opt-out check (`opted_out == True`) → **BLOCKED**
  2. Terminal action check (`STOP_AND_FLAG`) → **BLOCKED**
  3. Max retry limit check (`len(contact_history) >= max_retries`) → **BLOCKED**
  4. Cooldown window check (`elapsed_hours < min_gap_hours`) → **BLOCKED**
  5. Default → **ALLOWED**
- **Global Batch Cap**: Prevents automated runaway spam across the portfolio.

### `src/audit.py`
- **Purpose**: Writes immutable JSON Lines entries to `logs/audit_trail.jsonl` capturing transaction ID, timestamp, failure code, root cause, chosen action, guardrail decision, outreach message, and final outcome.

### `src/baseline.py` & `src/metrics.py` & `src/run_batch.py`
- **Purpose**: Simulates the legacy blind-retry baseline (retrying every 24h up to 3 times with generic copy) alongside the intelligent AutoPey-Rescue system.
- **Output**: Exports comparative metrics to `data/results.json`.

### `dashboard/app.py`
- **Purpose**: Interactive Streamlit web application showcasing executive KPI benchmarks, audit explorer, transaction spotlight walkthrough, and interactive live recovery simulation.
