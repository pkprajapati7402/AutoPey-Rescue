# Autopay Rescue — Project Planning

**Track:** 03 — AI Revenue Recovery
**One-line pitch:** An agent that diagnoses *why* a UPI Autopay/e-mandate payment failed, and takes a different, bounded action for each root cause — instead of retrying blindly.

---

## 1. Problem statement

Subscription businesses on UPI Autopay lose recurring revenue every month because failed mandate debits get retried the same way regardless of why they failed — a technical timeout, an empty account, and an expired mandate all get the same blind "try again tomorrow." That wastes retries on failures that will never recover, annoys customers who've already cancelled, and misses failures that could recover with the right nudge at the right time.

Autopay Rescue closes that loop: **detect → diagnose root cause → choose the right intervention → act within bounds → log everything → measure the result against a naive baseline.**

## 2. Why this fits the evaluation bar

| Criterion (as reported for this buildathon) | How this project answers it |
|---|---|
| Problem taste | A specific, boring-but-real fintech problem — not a generic chatbot |
| Build quality | Clean module boundaries, reproducible batch run, real logs |
| AI judgment | Diagnosis and policy are deterministic rules; the LLM is used only where it earns its keep (message drafting, promise-to-pay parsing) |
| Failure recovery | The build log (Phase 10) captures a real thing that broke and how it was fixed — this feeds directly into the form's "Build Challenges" field |

## 3. Scope

**In scope**
- Synthetic batch of failed mandate transactions (no real bank/PSP connection needed)
- Deterministic root-cause diagnosis across 4 failure categories
- Per-category intervention policy with guardrails
- LLM-drafted Hinglish outreach message + simple promise-to-pay capture
- Full audit trail per transaction
- Batch run comparing this system's recovery rate against a naive blind-retry baseline
- A minimal dashboard to view the results for the demo video

**Explicitly out of scope (cut these first if time runs short)**
- Real WhatsApp/SMS sending (log the message instead of sending it)
- Real bank/mandate integration
- More than 4 failure categories
- User auth, multi-tenant support, persistence beyond a local file/DB
- Anything resembling a production deployment

## 4. Architecture

```
                ┌─────────────────────┐
                │  Synthetic Data Gen  │
                └──────────┬───────────┘
                           │ failed_transactions.json
                           ▼
                ┌─────────────────────┐
                │   Diagnosis Engine   │  (deterministic rules)
                └──────────┬───────────┘
                           │ root_cause
                           ▼
                ┌─────────────────────┐
                │   Policy Engine      │  (per-category action)
                └──────────┬───────────┘
                           │ chosen_action
              ┌────────────┼────────────┐
              ▼                         ▼
     ┌─────────────────┐      ┌──────────────────┐
     │  Retry Scheduler │      │  Outreach (LLM)   │  Hinglish nudge +
     └────────┬─────────┘      │  promise-to-pay   │  promise-to-pay parse
              │                └─────────┬─────────┘
              └────────────┬─────────────┘
                           ▼
                ┌─────────────────────┐
                │      Guardrails      │  (caps, cooldowns, opt-out, stop)
                └──────────┬───────────┘
                           ▼
                ┌─────────────────────┐
                │     Audit Trail      │  → logs/audit_trail.jsonl
                └──────────┬───────────┘
                           ▼
                ┌─────────────────────┐
                │  Metrics + Baseline   │  → results.json
                └──────────┬───────────┘
                           ▼
                ┌─────────────────────┐
                │   Demo Dashboard      │  (Streamlit)
                └─────────────────────┘
```

## 5. Tech stack (optimized for speed of build, not for showing off)

- **Python 3.11+** — fastest path to a working rule engine + LLM calls + a runnable batch script
- **Anthropic or OpenAI API** for the LLM-drafted outreach messages
- **Streamlit** for the demo dashboard — a working UI in under an hour, no frontend build needed
- **Plain JSON/JSONL files** for data and logs — no database needed at this scale; swap for SQLite only if it's genuinely faster than fighting file I/O
- **pytest** for a handful of tests on the diagnosis and guardrail logic — cheap insurance against an embarrassing bug in the demo

## 6. Data model

```json
{
  "transaction_id": "TXN00042",
  "subscription_id": "SUB00019",
  "customer_id": "CUST00019",
  "customer_name": "Rohit Sharma",
  "amount_inr": 499,
  "due_date": "2026-08-28",
  "failure_code": "INSUFFICIENT_BALANCE",
  "attempt_number": 1,
  "opted_out": false,
  "created_at": "2026-08-28T09:14:00Z"
}
```

`failure_code` ∈ `{TECH_TIMEOUT, INSUFFICIENT_BALANCE, MANDATE_EXPIRED, HARD_DECLINE_OR_CANCELLED}`

## 7. Diagnosis → policy table

| Failure code | Root cause | Action | Max retries | Min gap |
|---|---|---|---|---|
| `TECH_TIMEOUT` | Transient, not the customer's fault | Auto-retry same day | 2 | 4 hours |
| `INSUFFICIENT_BALANCE` | Timing issue | Hold, retry near likely salary date + one Hinglish nudge with promise-to-pay capture | 2 | 48 hours |
| `MANDATE_EXPIRED` | Needs customer action | Send one re-authorization link, no retry until they act | 1 | — |
| `HARD_DECLINE_OR_CANCELLED` | Terminal | Stop immediately, flag for human review | 0 | — |

## 8. Guardrails (must be visible in code, not just described)

- Hard retry caps per the table above, enforced in code, not just documented
- No two contacts to the same customer within the min-gap window
- Immediate, permanent stop on `opted_out: true` or terminal category
- Global cap on nudges sent per batch run (avoid a spam-shaped result even in simulation)

## 9. Baseline for comparison

Naive policy: retry every 24 hours, up to 3 attempts, same generic message, no category logic, no stop conditions until attempts run out.

## 10. Metrics to report

- Recovery rate (%) — system vs. baseline
- ₹ recovered — system vs. baseline
- Total customer contacts — system vs. baseline
- Recovered-per-contact ratio — system vs. baseline (this is the number that should look best; it's the one that answers "does bounded beat blind")
- Average days-to-recovery

## 11. Deliverables checklist

- [ ] Public GitHub repo, clean structure, README with setup + run instructions
- [ ] `results.json` / dashboard screenshot showing system vs. baseline numbers
- [ ] `logs/audit_trail.jsonl` — one entry per decision, readable
- [ ] 5-minute pitch video (you're building this yourself)
- [ ] One real "what broke and how I fixed it" story, captured while building, for the form

## 12. Rough timeline

| Day | Focus |
|---|---|
| Day 1 | Phases 0–3: setup, data generator, diagnosis engine, policy engine — get one ugly end-to-end run working |
| Day 2 | Phases 4–7: LLM outreach, guardrails, audit trail, metrics + baseline |
| Day 3 | Phases 8–10: dashboard, docs, test run, record video, submit |

## 13. Manual steps only you can do

- Create the GitHub repo and push
- Get an LLM API key (Anthropic or OpenAI) and set it as an environment variable — never commit it
- Decide whether to attempt the optional Razorpay test-mode stretch integration (see instruction.md Phase 11) — skip it if Day 3 arrives and it isn't done
- Record and edit the 5-minute video
- Fill in the real numbers from your own batch run into the application form — don't estimate them

## 14. Risks

| Risk | Mitigation |
|---|---|
| Running out of time before a full loop works | Cut to 3 failure categories, drop the dashboard, show `results.json` directly in the video |
| Synthetic data reads as fake/unrealistic | Base failure codes and ratios on real UPI Autopay decline categories, vary amounts and customer names, don't make every case a clean win |
| System's numbers happen to look worse than baseline on some runs | Report it honestly and explain why — that's a stronger signal than a suspiciously perfect result |
