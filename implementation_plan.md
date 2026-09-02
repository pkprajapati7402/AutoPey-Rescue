# AutoPey Rescue — Maturity Upgrade Plan

## Assessment: Current vs. Winning State

### What's Already Solid
- All 29 tests pass (clean, well-structured)
- Core pipeline: diagnosis → policy → guardrails → audit → metrics fully operational
- Smart baseline comparison with compelling numbers (4.28x efficiency advantage)
- Real audit trail in JSONL format

### What Needs Upgrading

1. **Deprecated LLM API** — `google-generativeai` is EOL → migrate to `google-genai` SDK
2. **Outreach module** — Currently returning fallback template for everyone. Need real Gemini calls with new API
3. **Promise-to-Pay Feedback Loop** — Missing escalation workflow: what happens after a customer says "kal karta hun"? Need a tracker
4. **Dashboard** — Good structure but not demo-stunning. Need: 
   - Recovery funnel chart
   - Per-failure-code breakdown
   - Promise tracker panel
   - Much richer visual design
5. **Escalation Engine** — No `src/escalation.py` module. Need promise-to-pay tracking with follow-up scheduling
6. **Missing `python-dateutil` in requirements.txt** — guardrails.py uses it
7. **Data generator enhancement** — Add `merchant_category`, `risk_score`, `customer_segment` fields for richer analysis
8. **Batch runner** — Add promise-to-pay simulation loop (customer responses, follow-up nudges)
9. **README** — Add Streamlit Cloud deployment badge and clearer demo instructions

## Upgrade Plan

### 1. Fix dependencies & SDK migration
- Add `python-dateutil` to requirements.txt
- Replace `google-generativeai` with `google-genai`
- Update outreach.py to use new SDK

### 2. Enhance Data Generator
- Add `risk_score`, `customer_segment`, `merchant_category`, `previous_failure_count`
- These enable richer segmentation in dashboard

### 3. Add Promise-to-Pay Tracker (`src/promise_tracker.py`)
- Tracks customer replies and promise dates
- Escalation rules: if promise date passes → escalate, if DECLINED → permanent stop
- Integrates with audit trail

### 4. Enhance Batch Runner
- Add promise-to-pay simulation (20% respond, mix of PROMISED/DECLINED/UNCLEAR)
- Track escalations and follow-up nudge count
- Enrich results.json with per-category breakdown

### 5. Upgrade Dashboard (Major)
- Recovery Funnel: At Risk → Contacted → Responded → Recovered
- Per-failure-code breakdown heatmap
- Promise Tracker panel with escalation queue  
- Enhanced audit trail with color-coded action badges
- Live demo section with richer interactivity
- Better visual design (gradients, better charts)

### 6. Add Escalation Module (`src/escalation.py`)
- classify_escalation(outcome): routes to human_review | retry_schedule | permanent_stop
- PROMISE_BROKEN → escalate to human review
- DECLINED + multiple contacts → permanent stop + CRM note
- Creates escalation_queue.jsonl

### 7. Final Verification
- Re-run full batch with new Gemini SDK
- Run all tests
- Launch dashboard and verify all views
