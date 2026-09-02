"""AutoPey-Rescue — Modern Streamlit Demo Dashboard.

Track: 03 — AI Revenue Recovery
An intelligent agent that diagnoses why UPI Autopay / e-mandates fail and takes
bounded, root-cause-specific actions instead of naive blind retries.
"""

import json
import os
import sys
import altair as alt
import pandas as pd
import streamlit as st

# Add repo root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audit import load_audit_trail
from src.diagnosis import diagnose, FAILURE_CODE_TO_ROOT_CAUSE
from src.policy import decide_action
from src.guardrails import is_action_allowed
from src.outreach import draft_nudge, parse_promise_to_pay, _get_api_provider

# Page Configuration
st.set_page_config(
    page_title="AutoPey Rescue — AI Revenue Recovery",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #10B981, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #94A3B8;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    .badge-success {
        background-color: #065F46;
        color: #34D399;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-danger {
        background-color: #881337;
        color: #FB7185;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-info {
        background-color: #1E3A8A;
        color: #93C5FD;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .whatsapp-bubble {
        background-color: #054C44;
        color: #E9EDEF;
        padding: 12px 16px;
        border-radius: 10px 10px 2px 10px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        font-size: 0.95rem;
        line-height: 1.4;
        border-left: 4px solid #25D366;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


def load_results_data() -> dict:
    """Load results.json or return empty dict if missing."""
    results_path = "data/results.json"
    if os.path.exists(results_path):
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# Sidebar Controls
with st.sidebar:
    st.image("https://raw.githubusercontent.com/feathericons/feather/master/icons/shield.svg", width=48)
    st.markdown("### **AutoPey-Rescue**")
    st.caption("AI-Powered UPI Mandate Recovery Agent")
    st.markdown("---")

    provider, _ = _get_api_provider()
    if provider:
        st.success(f"⚡ LLM Active: **{provider.upper()}**")
    else:
        st.info("ℹ️ LLM: **Offline Resilient Mode**")

    st.markdown("---")
    navigation = st.radio(
        "Navigation",
        ["📊 Executive Benchmark", "🔍 Audit Trail Explorer", "🎯 Transaction Spotlight", "🧪 Live Recovery Simulator"],
        index=0
    )

    st.markdown("---")
    st.markdown("""
    **Core Diagnostic Matrix:**
    - `TECH_TIMEOUT` → Auto-retry (4h gap)
    - `INSUFFICIENT_BALANCE` → Hold + Salary Nudge
    - `MANDATE_EXPIRED` → Re-auth Mandate Link
    - `HARD_DECLINE` → Terminal Stop (0 Retries)
    """)


# Header Section
st.markdown("<div class='main-header'>AutoPey Rescue — AI Revenue Recovery</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Diagnosing root causes in UPI Autopay failures and executing bounded, compliant interventions.</div>", unsafe_allow_html=True)

results_data = load_results_data()

# -------------------------------------------------------------
# TAB 1: EXECUTIVE BENCHMARK
# -------------------------------------------------------------
if navigation == "📊 Executive Benchmark":
    st.subheader("System Performance vs Naive Blind-Retry Baseline")

    if not results_data:
        st.warning("⚠️ No benchmark results found. Run `python src/run_batch.py` to generate results.")
    else:
        sys_m = results_data.get("system", {}).get("metrics", {})
        base_m = results_data.get("baseline", {}).get("metrics", {})

        # Top KPI Scorecard
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            diff_rec = round(sys_m.get("recovery_rate_pct", 0) - base_m.get("recovery_rate_pct", 0), 2)
            st.metric(
                label="Recovery Rate (%)",
                value=f"{sys_m.get('recovery_rate_pct', 0)}%",
                delta=f"{diff_rec:+}% vs Baseline"
            )

        with col2:
            diff_inr = sys_m.get("total_recovered_inr", 0) - base_m.get("total_recovered_inr", 0)
            st.metric(
                label="Revenue Recovered",
                value=f"₹{sys_m.get('total_recovered_inr', 0):,}",
                delta=f"+₹{diff_inr:,} Added Value"
            )

        with col3:
            contact_reduction = base_m.get("total_contacts", 0) - sys_m.get("total_contacts", 0)
            st.metric(
                label="Total Contacts Sent",
                value=f"{sys_m.get('total_contacts', 0)}",
                delta=f"-{contact_reduction} Spam Reductions",
                delta_color="inverse"
            )

        with col4:
            base_eff = base_m.get("recovered_per_contact", 1)
            sys_eff = sys_m.get("recovered_per_contact", 0)
            multiplier = round(sys_eff / base_eff, 2) if base_eff > 0 else 1.0
            st.metric(
                label="₹ Recovered / Contact",
                value=f"₹{sys_eff:,.2f}",
                delta=f"{multiplier}x Efficiency Multiplier"
            )

        st.markdown("---")

        # Side-by-side Visual Charts
        chart_col1, chart_col2 = st.columns(2)

        chart_data_summary = pd.DataFrame([
            {"Policy": "Naive Blind Retry", "Metric": "Recovery Rate (%)", "Value": base_m.get("recovery_rate_pct", 0)},
            {"Policy": "AutoPey Rescue", "Metric": "Recovery Rate (%)", "Value": sys_m.get("recovery_rate_pct", 0)},
            {"Policy": "Naive Blind Retry", "Metric": "Total Contacts", "Value": base_m.get("total_contacts", 0)},
            {"Policy": "AutoPey Rescue", "Metric": "Total Contacts", "Value": sys_m.get("total_contacts", 0)},
            {"Policy": "Naive Blind Retry", "Metric": "₹ / Contact", "Value": base_m.get("recovered_per_contact", 0)},
            {"Policy": "AutoPey Rescue", "Metric": "₹ / Contact", "Value": sys_m.get("recovered_per_contact", 0)},
        ])

        with chart_col1:
            st.markdown("#### 📈 Efficiency Comparison: ₹ Recovered Per Customer Contact")
            eff_df = pd.DataFrame({
                "Strategy": ["Naive Baseline (Blind 24h)", "AutoPey Rescue (Intelligent)"],
                "INR_Per_Contact": [base_m.get("recovered_per_contact", 0), sys_m.get("recovered_per_contact", 0)]
            })
            chart1 = alt.Chart(eff_df).mark_bar(cornerRadius=8, size=40).encode(
                x=alt.X("Strategy:N", title="Recovery Strategy", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("INR_Per_Contact:Q", title="INR Recovered / Contact (₹)"),
                color=alt.Color("Strategy:N", scale=alt.Scale(range=["#EF4444", "#10B981"]), legend=None)
            ).properties(height=320)
            st.altair_chart(chart1, use_container_width=True)

        with chart_col2:
            st.markdown("#### 📉 Customer Spam Reduction (Total Contacts)")
            contacts_df = pd.DataFrame({
                "Strategy": ["Naive Baseline (Blind 24h)", "AutoPey Rescue (Intelligent)"],
                "Total_Contacts": [base_m.get("total_contacts", 0), sys_m.get("total_contacts", 0)]
            })
            chart2 = alt.Chart(contacts_df).mark_bar(cornerRadius=8, size=40).encode(
                x=alt.X("Strategy:N", title="Recovery Strategy", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("Total_Contacts:Q", title="Total Contacts Dispatched"),
                color=alt.Color("Strategy:N", scale=alt.Scale(range=["#F59E0B", "#3B82F6"]), legend=None)
            ).properties(height=320)
            st.altair_chart(chart2, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 📋 Comprehensive Comparison Matrix")
        table_df = pd.DataFrame({
            "Evaluation Metric": [
                "Portfolio Size Analyzed",
                "Total Amount At Risk",
                "Recovery Rate (%)",
                "Total Revenue Recovered",
                "Total Customer Contacts",
                "Recovered ₹ per Contact",
                "Average Days to Recovery",
                "Customer Opt-Out Adherence",
                "Terminal Decline Handling"
            ],
            "Naive Blind Retry (Legacy)": [
                f"{base_m.get('total_transactions', 0)} mandates",
                f"₹{base_m.get('total_at_risk_inr', 0):,}",
                f"{base_m.get('recovery_rate_pct', 0)}%",
                f"₹{base_m.get('total_recovered_inr', 0):,}",
                f"{base_m.get('total_contacts', 0)} touches",
                f"₹{base_m.get('recovered_per_contact', 0):,.2f}",
                f"{base_m.get('avg_days_to_recovery', 0)} days",
                "❌ Ignored (retries anyway)",
                "❌ Wastes 3 blind attempts"
            ],
            "AutoPey Rescue (Smart Agent)": [
                f"{sys_m.get('total_transactions', 0)} mandates",
                f"₹{sys_m.get('total_at_risk_inr', 0):,}",
                f"{sys_m.get('recovery_rate_pct', 0)}%",
                f"₹{sys_m.get('total_recovered_inr', 0):,}",
                f"{sys_m.get('total_contacts', 0)} touches",
                f"₹{sys_m.get('recovered_per_contact', 0):,.2f}",
                f"{sys_m.get('avg_days_to_recovery', 0)} days",
                "✅ 100% Guaranteed Stop",
                "✅ Immediate Stop & Flag"
            ]
        })
        st.dataframe(table_df, use_container_width=True, hide_index=True)


# -------------------------------------------------------------
# TAB 2: AUDIT TRAIL EXPLORER
# -------------------------------------------------------------
elif navigation == "🔍 Audit Trail Explorer":
    st.subheader("Immutable Audit Trail & Decision Ledger")
    st.caption("Every diagnostic check, policy choice, guardrail evaluation, and outreach message is logged immutably to logs/audit_trail.jsonl.")

    audit_records = load_audit_trail()

    if not audit_records:
        st.warning("⚠️ No audit records found in `logs/audit_trail.jsonl`. Run `python src/run_batch.py` to generate the log.")
    else:
        df_audit = pd.DataFrame(audit_records)

        # Filters
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            fc_filter = st.multiselect(
                "Filter by Failure Code",
                options=list(df_audit["failure_code"].unique()) if "failure_code" in df_audit else [],
                default=[]
            )
        with f_col2:
            status_filter = st.selectbox(
                "Filter by Guardrail Status",
                options=["All", "Allowed Only", "Blocked Only"],
                index=0
            )
        with f_col3:
            search_query = st.text_input("Search Customer Name / Txn ID", "")

        filtered_df = df_audit.copy()

        if fc_filter:
            filtered_df = filtered_df[filtered_df["failure_code"].isin(fc_filter)]

        if status_filter == "Allowed Only":
            filtered_df = filtered_df[filtered_df["was_allowed"] == True]
        elif status_filter == "Blocked Only":
            filtered_df = filtered_df[filtered_df["was_allowed"] == False]

        if search_query:
            q = search_query.lower()
            filtered_df = filtered_df[
                filtered_df["transaction_id"].str.lower().str.contains(q, na=False) |
                filtered_df["customer_name"].str.lower().str.contains(q, na=False)
            ]

        st.markdown(f"**Showing {len(filtered_df)} of {len(df_audit)} log entries:**")

        # Display clean view
        display_cols = [
            "timestamp", "transaction_id", "customer_name", "amount_inr",
            "failure_code", "root_cause", "chosen_action", "was_allowed", "block_reason"
        ]
        available_cols = [c for c in display_cols if c in filtered_df.columns]
        st.dataframe(filtered_df[available_cols], use_container_width=True, hide_index=True)


# -------------------------------------------------------------
# TAB 3: TRANSACTION SPOTLIGHT
# -------------------------------------------------------------
elif navigation == "🎯 Transaction Spotlight":
    st.subheader("Single Transaction End-to-End Walkthrough")
    st.caption("Inspect the complete diagnostic lifecycle and intervention timeline for any individual mandate.")

    audit_records = load_audit_trail()

    if not audit_records:
        st.warning("⚠️ No audit records found. Run `python src/run_batch.py` first.")
    else:
        txn_ids = sorted(list({r["transaction_id"] for r in audit_records if "transaction_id" in r}))
        selected_txn_id = st.selectbox("Select Transaction ID to Spotlight", options=txn_ids, index=0)

        matching_entries = [r for r in audit_records if r.get("transaction_id") == selected_txn_id]

        if matching_entries:
            first_entry = matching_entries[0]
            last_entry = matching_entries[-1]

            s_col1, s_col2, s_col3, s_col4 = st.columns(4)
            with s_col1:
                st.markdown(f"**Customer:** {first_entry.get('customer_name')}")
                st.markdown(f"**Customer ID:** `{first_entry.get('customer_id')}`")
            with s_col2:
                st.markdown(f"**Amount:** ₹{first_entry.get('amount_inr')}")
                st.markdown(f"**Due Date:** {first_entry.get('due_date')}")
            with s_col3:
                st.markdown(f"**Failure Code:** `{first_entry.get('failure_code')}`")
                st.markdown(f"**Root Cause:** `{first_entry.get('root_cause')}`")
            with s_col4:
                st.markdown(f"**Policy Action:** `{first_entry.get('chosen_action')}`")
                allowed_str = "✅ Allowed" if first_entry.get("was_allowed") else f"🚫 Blocked ({first_entry.get('block_reason')})"
                st.markdown(f"**Guardrail:** {allowed_str}")

            st.markdown("---")

            # WhatsApp Message Preview if available
            has_message = any(e.get("outreach_message") for e in matching_entries)
            if has_message:
                st.markdown("#### 📱 Hinglish WhatsApp Outreach Message (Simulated)")
                for e in matching_entries:
                    msg = e.get("outreach_message")
                    if msg:
                        st.markdown(f"""
                        <div class="whatsapp-bubble">
                            <b>AutoPey Concierge (WhatsApp)</b><br>
                            {msg}<br>
                            <small style="color: #94A3B8;">Sent at {e.get('timestamp')}</small>
                        </div>
                        """, unsafe_allow_html=True)

            # Execution timeline trace
            st.markdown("#### 📜 Decision & Outcome Trace")
            for idx, entry in enumerate(matching_entries, 1):
                with st.expander(f"Step {idx}: {entry.get('chosen_action')} @ {entry.get('timestamp')}", expanded=True):
                    st.json(entry)


# -------------------------------------------------------------
# TAB 4: LIVE RECOVERY SIMULATOR
# -------------------------------------------------------------
elif navigation == "🧪 Live Recovery Simulator":
    st.subheader("Interactive Intent Classifier & Mandate Simulation")
    st.caption("Test the Gemini LLM Hinglish nudge generator and promise-to-pay intent parser in real time.")

    sim_tab1, sim_tab2 = st.tabs(["💬 Promise-to-Pay Intent Classifier", "⚙️ Live Mandate Failure Simulator"])

    with sim_tab1:
        st.markdown("#### Test Customer WhatsApp Replies")
        st.markdown("Type a customer reply in Hinglish or English to see how the AI parses intent:")

        preset_replies = [
            "Haan kal pakka pay kar dunga",
            "Salary aane do 5th ko tab automatic ho jayega",
            "Band karo ye subscription, I have already cancelled",
            "Aaj shaam 7 baje karunga",
            "Who is this? Fraud message lag raha hai"
        ]
        selected_preset = st.selectbox("Or choose a sample reply:", ["-- Custom Input --"] + preset_replies)

        reply_input = st.text_area(
            "Customer Reply Text:",
            value="" if selected_preset == "-- Custom Input --" else selected_preset,
            placeholder="Type Hinglish customer reply here..."
        )

        if st.button("🚀 Parse Intent with LLM", type="primary"):
            if not reply_input.strip():
                st.error("Please enter a reply message.")
            else:
                with st.spinner("Analyzing intent with LLM..."):
                    intent_result = parse_promise_to_pay(reply_input)

                st.markdown("##### Classification Result:")
                status = intent_result.get("status")
                date = intent_result.get("promised_date")

                if status == "PROMISED":
                    st.success(f"**Intent Status:** `{status}` 🎉")
                    if date:
                        st.info(f"**Extracted Promise Date:** `{date}` (Scheduler will hold retry until this date)")
                    else:
                        st.info("**Extracted Promise Date:** Generic promise captured")
                elif status == "DECLINED":
                    st.error(f"**Intent Status:** `{status}` 🛑 (Guardrail will permanently stop retries and update CRM)")
                else:
                    st.warning(f"**Intent Status:** `{status}` ⚠️ (Routed to customer support team)")

                st.json(intent_result)

    with sim_tab2:
        st.markdown("#### Test Custom Failed Mandate Scenario")
        c1, c2 = st.columns(2)
        with c1:
            test_name = st.text_input("Customer Name", "Ananya Verma")
            test_amount = st.number_input("Amount (INR)", value=499, step=100)
            test_due = st.date_input("Due Date")
        with c2:
            test_code = st.selectbox("Failure Code", list(FAILURE_CODE_TO_ROOT_CAUSE.keys()))
            test_opted_out = st.checkbox("Customer Opted Out?", value=False)

        if st.button("⚡ Run Live Diagnostic Pipeline"):
            txn = {
                "transaction_id": "TEST_TXN_999",
                "customer_name": test_name,
                "amount_inr": test_amount,
                "due_date": str(test_due),
                "failure_code": test_code,
                "opted_out": test_opted_out,
            }

            # 1. Diagnose
            root_cause = diagnose(txn)
            # 2. Policy
            policy = decide_action(txn, root_cause)
            # 3. Guardrails
            guardrail = is_action_allowed(txn, policy, contact_history=[])
            # 4. Outreach
            nudge_msg = draft_nudge(txn) if guardrail["allowed"] and policy["action"] in ["HOLD_AND_NUDGE", "REAUTH_LINK"] else None

            st.markdown("---")
            st.markdown("##### Pipeline Evaluation:")
            res_col1, res_col2, res_col3 = st.columns(3)
            with res_col1:
                st.metric("Diagnosed Root Cause", root_cause)
            with res_col2:
                st.metric("Policy Action", policy["action"])
            with res_col3:
                status_txt = "✅ Allowed" if guardrail["allowed"] else f"🚫 Blocked ({guardrail['reason']})"
                st.metric("Guardrail Status", status_txt)

            if nudge_msg:
                st.markdown("##### Generated Hinglish WhatsApp Outreach:")
                st.markdown(f"""
                <div class="whatsapp-bubble">
                    <b>AutoPey Concierge (WhatsApp)</b><br>
                    {nudge_msg}
                </div>
                """, unsafe_allow_html=True)
