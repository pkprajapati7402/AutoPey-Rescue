# 🛡️ AutoPey Rescue — AI Revenue Recovery

**Track:** 03 — AI Revenue Recovery  
**One-Line Pitch:** An intelligent agent that diagnoses *why* a UPI Autopay / e-mandate payment failed and executes bounded, root-cause-specific interventions instead of naive blind retries.

---

## 1. The Problem

Subscription businesses in India lose recurring revenue every month because failed UPI Autopay mandate debits get retried the same way regardless of why they failed. A technical bank timeout, an insufficient balance, an expired mandate, and a cancelled card all receive the identical blind *"retry again tomorrow"* treatment.

This legacy approach:
1. **Wastes retries** on failures that can never recover (expired or cancelled mandates).
2. **Annoys customers** who already cancelled with spammy payment failure alerts.
3. **Misses recoverable revenue** by failing to align retries with customer salary cycles or mandate re-authorization workflows.

---

## 2. The AutoPey Rescue Solution

AutoPey-Rescue introduces a closed-loop intelligence architecture:
$$\text{Detect} \longrightarrow \text{Diagnose Root Cause} \longrightarrow \text{Intervene Within Bounds} \longrightarrow \text{Audit Log} \longrightarrow \text{Benchmark}$$

### System Architecture

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

## 3. Verified Benchmark Results (200 Transaction Portfolio)

Running the batch benchmark on a realistic Indian subscription distribution yields the following verified numbers:

| Evaluation Metric | Naive Blind Retry (Legacy) | AutoPey Rescue (Intelligent Agent) | Net Improvement |
|---|---|---|---|
| **Recovery Rate (%)** | 57.0% | **62.5%** | **+5.5% Higher Recovery** |
| **Total Revenue Recovered** | INR 57,986.00 | **INR 67,475.00** | **+INR 9,489.00 Extra Cash** |
| **Total Customer Contacts** | 445 touches | **121 touches** | **-72.8% Spam Reduction** |
| **Recovered INR / Contact** | INR 130.31 | **INR 557.64** | **4.28x Higher Efficiency** |
| **Average Days to Recovery** | 1.64 days | **1.29 days** | **Faster Cash Inflow** |
| **Opt-Out Compliance** | ❌ Retries blindly | **✅ 100% Immediate Stop** | **Zero Compliance Risk** |
| **Terminal Declines** | ❌ Wastes 3 attempts | **✅ Immediate Stop & Flag** | **Zero Wasted Attempts** |

---

## 4. Key Engineering Highlights

1. **Deterministic Core for Financial Operations**:
   - Diagnosis (`src/diagnosis.py`) and Policy mapping (`src/policy.py`) use deterministic lookup rules. No non-deterministic LLM hallucinations in core banking logic.
2. **Deliberate LLM Integration (Google Gemini)**:
   - LLMs are reserved exclusively for tone-sensitive Hinglish copy generation and fuzzy customer intent classification (*"promise to pay"*).
   - Supports **Google Gemini API** (Free tier / production via `GEMINI_API_KEY`), OpenAI, Anthropic, and resilient offline fallback templates.
3. **Financial Safety Guardrails**:
   - Hard retry limits, cooldown periods, opt-out enforcement, and global batch rate caps (`src/guardrails.py`).
4. **Append-Only Immutable Audit Trail**:
   - Every single check, evaluation, and outcome is logged to `logs/audit_trail.jsonl` (`src/audit.py`).
5. **Interactive Streamlit Demo Dashboard**:
   - Executive scorecards, comparative charts, audit trail search/filter, single-transaction spotlight, and live WhatsApp simulator (`dashboard/app.py`).

---

## 5. Repository Structure

```
AutoPey-Rescue/
├── README.md                     # Project overview and run guide
├── Planning.md                   # System design & evaluation bar
├── Instructions.md               # Phase-by-phase build guidelines
├── requirements.txt              # Dependencies (Gemini, Streamlit, Pytest, Pandas)
├── .env.example                  # Environment configuration template
├── .gitignore                    # Git exclusions
├── data/
│   ├── synthetic_transactions.json # 200 synthetic failed mandate records
│   └── results.json              # Side-by-side benchmark output
├── logs/
│   └── audit_trail.jsonl         # Append-only structured decision ledger
├── src/
│   ├── __init__.py
│   ├── data_generator.py         # Synthetic UPI Autopay data generator
│   ├── diagnosis.py              # Rule-based failure code classification
│   ├── policy.py                 # Intervention policy engine
│   ├── outreach.py               # Gemini Hinglish copy & promise-to-pay intent parser
│   ├── guardrails.py             # Safety constraints & cooldown enforcement
│   ├── audit.py                  # Structured audit logger & loader
│   ├── baseline.py               # Naive 24h blind retry simulation
│   ├── metrics.py                # Revenue & efficiency KPI calculator
│   └── run_batch.py              # End-to-end benchmark orchestrator
├── dashboard/
│   └── app.py                    # Streamlit interactive demo dashboard
├── docs/
│   ├── architecture.md           # Deep-dive module architecture
│   └── what_broke.md             # Real build challenges and solutions log
└── tests/
    ├── test_data_generator.py
    ├── test_diagnosis.py
    ├── test_policy.py
    ├── test_outreach.py
    ├── test_guardrails.py
    ├── test_audit.py
    ├── test_metrics.py
    └── test_pipeline.py
```

---

## 6. Quick Start & Setup

### Prerequisites
- Python 3.10+ (Tested on Python 3.13)
- Optional: Free Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
Copy `.env.example` to `.env` and add your Gemini API key:
```bash
copy .env.example .env
```
*(Note: If no API key is provided, the system seamlessly runs in offline resilient fallback mode with zero errors).*

### 3. Generate Synthetic Mandate Batch
```bash
python src/data_generator.py --count 200
```

### 4. Run the Batch Recovery Benchmark
```bash
python src/run_batch.py
```

### 5. Launch the Streamlit Demo Dashboard
```bash
streamlit run dashboard/app.py
```

### 6. Run Test Suite
```bash
python -m pytest -v
```

---

## 7. What is Real vs. What is Simulated

- **Real in Code**:
  - All diagnosis, policy, guardrail, audit trail, metrics calculation, and Streamlit UI code is 100% operational.
  - LLM message drafting and intent parsing call real Gemini / LLM APIs when keys are set.
- **Simulated for Demonstration**:
  - The transaction dataset is synthetically generated to mirror real-world UPI decline ratios.
  - WhatsApp messages and payment links are drafted and logged to `logs/audit_trail.jsonl` rather than dispatched to live telco/SMS networks.
  - Recovery outcomes are probabilistically simulated based on empirical banking recovery rates.

---

## 8. Documentation Links

- [System Architecture Deep-Dive](docs/architecture.md)
- [Build Challenges & Technical Obstacles (Phase 10)](docs/what_broke.md)