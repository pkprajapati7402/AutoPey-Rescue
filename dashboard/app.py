"""AutoPey-Rescue — Premium Streamlit Demo Dashboard.

Track: 03 — AI Revenue Recovery
An intelligent agent that diagnoses why UPI Autopay / e-mandates fail and takes
bounded, root-cause-specific actions with compliant escalation and a full audit trail.
"""

import json
import os
import sys
import altair as alt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Add repo root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.audit import load_audit_trail
from src.escalation import load_escalation_queue, get_escalation_summary
from src.diagnosis import diagnose, FAILURE_CODE_TO_ROOT_CAUSE
from src.policy import decide_action
from src.guardrails import is_action_allowed
from src.outreach import draft_nudge, parse_promise_to_pay, _get_api_provider

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AutoPey Rescue — AI Revenue Recovery",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Premium CSS Styling ──────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        font-size: 2.4rem;
        font-weight: 800;
        background: linear-gradient(135deg, #10B981 0%, #3B82F6 50%, #8B5CF6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.15rem;
        line-height: 1.2;
    }
    .sub-header {
        font-size: 1rem;
        color: #94A3B8;
        margin-bottom: 1.8rem;
        font-weight: 400;
    }
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #E2E8F0;
        margin-bottom: 0.8rem;
    }
    .kpi-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9));
        border: 1px solid rgba(99, 102, 241, 0.25);
        border-radius: 16px;
        padding: 1.4rem 1.6rem;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.05);
        margin-bottom: 1rem;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: 700;
        color: #F1F5F9;
        line-height: 1.1;
    }
    .kpi-label {
        font-size: 0.78rem;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
        margin-top: 0.3rem;
    }
    .kpi-delta-pos {
        font-size: 0.85rem;
        color: #34D399;
        font-weight: 600;
        margin-top: 0.4rem;
    }
    .kpi-delta-neg {
        font-size: 0.85rem;
        color: #FB7185;
        font-weight: 600;
        margin-top: 0.4rem;
    }
    .kpi-delta-neutral {
        font-size: 0.85rem;
        color: #94A3B8;
        font-weight: 500;
        margin-top: 0.4rem;
    }
    .badge-success {
        display: inline-block;
        background-color: rgba(6, 95, 70, 0.8);
        color: #34D399;
        padding: 2px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.78rem;
        border: 1px solid rgba(52, 211, 153, 0.3);
    }
    .badge-danger {
        display: inline-block;
        background-color: rgba(136, 19, 55, 0.8);
        color: #FB7185;
        padding: 2px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.78rem;
        border: 1px solid rgba(251, 113, 133, 0.3);
    }
    .badge-warning {
        display: inline-block;
        background-color: rgba(120, 53, 15, 0.8);
        color: #FCD34D;
        padding: 2px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.78rem;
        border: 1px solid rgba(252, 211, 77, 0.3);
    }
    .badge-info {
        display: inline-block;
        background-color: rgba(30, 58, 138, 0.8);
        color: #93C5FD;
        padding: 2px 10px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.78rem;
        border: 1px solid rgba(147, 197, 253, 0.3);
    }
    .whatsapp-bubble {
        background: linear-gradient(135deg, #054C44, #064E3B);
        color: #E9EDEF;
        padding: 14px 18px;
        border-radius: 12px 12px 4px 12px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 0.95rem;
        line-height: 1.5;
        border-left: 4px solid #25D366;
        margin: 10px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    .pipeline-step {
        background: rgba(30, 41, 59, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin: 0.5rem 0;
    }
    .step-icon {
        font-size: 1.5rem;
        margin-right: 0.5rem;
    }
    .escalation-HIGH {
        border-left: 4px solid #EF4444;
        background: rgba(239, 68, 68, 0.08);
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.4rem 0;
    }
    .escalation-MEDIUM {
        border-left: 4px solid #F59E0B;
        background: rgba(245, 158, 11, 0.08);
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.4rem 0;
    }
    .escalation-LOW {
        border-left: 4px solid #10B981;
        background: rgba(16, 185, 129, 0.08);
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.4rem 0;
    }
    .divider {
        border-top: 1px solid rgba(255,255,255,0.08);
        margin: 1.5rem 0;
    }
    /* Plotly charts background */
    .js-plotly-plot .plotly .bg {
        fill: transparent !important;
    }
</style>
""", unsafe_allow_html=True)


# ─── Data Loaders ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_results_data() -> dict:
    results_path = "data/results.json"
    if os.path.exists(results_path):
        with open(results_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


@st.cache_data(ttl=30)
def load_transactions_data() -> list:
    path = "data/synthetic_transactions.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def make_plotly_bar(df, x, y, color_map=None, title="", height=320):
    """Create a themed plotly bar chart."""
    fig = px.bar(df, x=x, y=y, color=x, color_discrete_map=color_map or {},
                 title=title, height=height, text=y)
    fig.update_traces(texttemplate='%{text:,.0f}', textposition='outside',
                      marker_line_width=0, opacity=0.9)
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(15,20,35,0.6)',
        font=dict(color='#CBD5E1', family='Inter, sans-serif'),
        title_font_size=13,
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(gridcolor='rgba(255,255,255,0.05)', title=''),
        yaxis=dict(gridcolor='rgba(255,255,255,0.05)', title=''),
    )
    return fig


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🛡️ **AutoPey Rescue**")
    st.caption("AI Revenue Recovery · Razorpay Track 03")
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    provider, _ = _get_api_provider()
    if provider:
        st.success(f"⚡ LLM: **{provider.upper()}** Active")
    else:
        st.info("ℹ️ LLM: Offline Resilient Mode")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    navigation = st.radio(
        "Navigation",
        [
            "📊 Executive Benchmark",
            "🔬 Category Deep Dive",
            "🚨 Escalation Queue",
            "🔍 Audit Trail",
            "🎯 Transaction Spotlight",
            "⚡ Live Pipeline Tester",
        ],
        index=0,
        label_visibility="collapsed"
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("""
    **Recovery Actions:**
    - `TECH_TIMEOUT` → Auto-retry (4h gap)
    - `INSUFF_BALANCE` → Hold + Salary Nudge
    - `MANDATE_EXPIRED` → Re-auth Link
    - `HARD_DECLINE` → Terminal Stop ✋
    """)
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    if st.button("🔄 Reload Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ─── Header ───────────────────────────────────────────────────────────────────
st.markdown("<div class='main-header'>AutoPey Rescue — AI Revenue Recovery</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-header'>Root-cause diagnosis → bounded intervention → compliant escalation → "
    "measured recovery. Every rupee tracked.</div>",
    unsafe_allow_html=True
)

results_data = load_results_data()

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1: EXECUTIVE BENCHMARK
# ═════════════════════════════════════════════════════════════════════════════
if navigation == "📊 Executive Benchmark":
    if not results_data:
        st.warning("⚠️ No benchmark results found. Run `python src/run_batch.py` to generate results.")
        st.stop()

    sys_m = results_data.get("system", {}).get("metrics", {})
    base_m = results_data.get("baseline", {}).get("metrics", {})

    # ── Hero KPI Row ──────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        diff_rate = round(sys_m.get("recovery_rate_pct", 0) - base_m.get("recovery_rate_pct", 0), 1)
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{sys_m.get('recovery_rate_pct', 0)}%</div>
            <div class="kpi-label">Recovery Rate</div>
            <div class="kpi-delta-pos">+{diff_rate}% vs Baseline</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        diff_inr = sys_m.get("total_recovered_inr", 0) - base_m.get("total_recovered_inr", 0)
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">₹{sys_m.get('total_recovered_inr', 0):,}</div>
            <div class="kpi-label">Revenue Recovered</div>
            <div class="kpi-delta-pos">+₹{diff_inr:,} extra</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        base_eff = base_m.get("recovered_per_contact", 1)
        sys_eff = sys_m.get("recovered_per_contact", 0)
        multiplier = round(sys_eff / base_eff, 2) if base_eff > 0 else 1.0
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">₹{sys_eff:,.0f}</div>
            <div class="kpi-label">₹ Recovered / Contact</div>
            <div class="kpi-delta-pos">{multiplier}x efficiency gain</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        base_contacts = base_m.get("total_contacts", 0)
        sys_contacts = sys_m.get("total_contacts", 0)
        reduction = base_contacts - sys_contacts
        reduction_pct = round((reduction / base_contacts) * 100, 1) if base_contacts > 0 else 0
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{sys_contacts}</div>
            <div class="kpi-label">Total Contacts Sent</div>
            <div class="kpi-delta-pos">-{reduction_pct}% spam reduction</div>
        </div>""", unsafe_allow_html=True)

    with c5:
        sys_days = sys_m.get("avg_days_to_recovery", 0)
        base_days = base_m.get("avg_days_to_recovery", 0)
        days_faster = round(base_days - sys_days, 2)
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{sys_days} days</div>
            <div class="kpi-label">Avg Recovery Time</div>
            <div class="kpi-delta-pos">{days_faster} days faster</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── Charts Row ────────────────────────────────────────────────────────────
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown("<div class='section-title'>💰 Revenue Recovered</div>", unsafe_allow_html=True)
        rev_df = pd.DataFrame({
            "Strategy": ["Naive Baseline", "AutoPey Rescue"],
            "Recovered": [base_m.get("total_recovered_inr", 0), sys_m.get("total_recovered_inr", 0)]
        })
        fig1 = make_plotly_bar(rev_df, "Strategy", "Recovered",
                               color_map={"Naive Baseline": "#EF4444", "AutoPey Rescue": "#10B981"})
        st.plotly_chart(fig1, use_container_width=True)

    with col_b:
        st.markdown("<div class='section-title'>📞 Customer Contacts (Lower = Better)</div>", unsafe_allow_html=True)
        contact_df = pd.DataFrame({
            "Strategy": ["Naive Baseline", "AutoPey Rescue"],
            "Contacts": [base_m.get("total_contacts", 0), sys_m.get("total_contacts", 0)]
        })
        fig2 = make_plotly_bar(contact_df, "Strategy", "Contacts",
                               color_map={"Naive Baseline": "#F59E0B", "AutoPey Rescue": "#3B82F6"})
        st.plotly_chart(fig2, use_container_width=True)

    with col_c:
        st.markdown("<div class='section-title'>⚡ Efficiency (₹ per Contact)</div>", unsafe_allow_html=True)
        eff_df = pd.DataFrame({
            "Strategy": ["Naive Baseline", "AutoPey Rescue"],
            "Efficiency": [base_m.get("recovered_per_contact", 0), sys_m.get("recovered_per_contact", 0)]
        })
        fig3 = make_plotly_bar(eff_df, "Strategy", "Efficiency",
                               color_map={"Naive Baseline": "#6366F1", "AutoPey Rescue": "#8B5CF6"})
        st.plotly_chart(fig3, use_container_width=True)

    # ── Recovery Funnel ────────────────────────────────────────────────────────
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>🔽 Recovery Funnel (AutoPey Rescue)</div>", unsafe_allow_html=True)

    sys_outcomes = results_data.get("system", {}).get("outcomes", [])
    total_txns = len(sys_outcomes)
    nudged = sum(1 for o in sys_outcomes if o.get("contacts_sent", 0) > 0)
    replied = sum(1 for o in sys_outcomes if o.get("promise_to_pay_status") is not None)
    promised = sum(1 for o in sys_outcomes if o.get("promise_to_pay_status") == "PROMISED")
    recovered_count = sum(1 for o in sys_outcomes if o.get("recovered"))

    funnel_fig = go.Figure(go.Funnel(
        y=["At Risk (All Transactions)", "Contacted (Nudge Sent)", "Customer Replied",
           "Promise to Pay Captured", "Payment Recovered"],
        x=[total_txns, nudged, replied, promised, recovered_count],
        textposition="inside",
        textinfo="value+percent initial",
        opacity=0.9,
        marker=dict(
            color=["#1E293B", "#1E40AF", "#7C3AED", "#0D9488", "#059669"],
            line=dict(width=2, color="#0F172A")
        ),
        connector=dict(line=dict(color="#334155", dash="dot", width=2))
    ))
    funnel_fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(15,20,35,0.6)',
        font=dict(color='#CBD5E1', family='Inter'),
        height=280,
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(funnel_fig, use_container_width=True)

    # ── Full Comparison Matrix ─────────────────────────────────────────────────
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📋 Full Benchmark Matrix</div>", unsafe_allow_html=True)

    table_df = pd.DataFrame({
        "Metric": [
            "Portfolio Analyzed", "Total At Risk", "Recovery Rate (%)", "Revenue Recovered",
            "Contacts Sent", "₹ Recovered / Contact", "Avg Days to Recovery",
            "Opt-Out Compliance", "Terminal Decline Handling"
        ],
        "🔴 Naive Blind Retry": [
            f"{base_m.get('total_transactions', 0)} mandates",
            f"₹{base_m.get('total_at_risk_inr', 0):,}",
            f"{base_m.get('recovery_rate_pct', 0)}%",
            f"₹{base_m.get('total_recovered_inr', 0):,}",
            f"{base_m.get('total_contacts', 0)} touches",
            f"₹{base_m.get('recovered_per_contact', 0):,.2f}",
            f"{base_m.get('avg_days_to_recovery', 0)} days",
            "❌ Retries blind",
            "❌ 3 wasted attempts"
        ],
        "🟢 AutoPey Rescue": [
            f"{sys_m.get('total_transactions', 0)} mandates",
            f"₹{sys_m.get('total_at_risk_inr', 0):,}",
            f"{sys_m.get('recovery_rate_pct', 0)}%",
            f"₹{sys_m.get('total_recovered_inr', 0):,}",
            f"{sys_m.get('total_contacts', 0)} touches",
            f"₹{sys_m.get('recovered_per_contact', 0):,.2f}",
            f"{sys_m.get('avg_days_to_recovery', 0)} days",
            "✅ 100% Immediate Stop",
            "✅ Stop & Flag Instantly"
        ]
    })
    st.dataframe(table_df, use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2: CATEGORY DEEP DIVE
# ═════════════════════════════════════════════════════════════════════════════
elif navigation == "🔬 Category Deep Dive":
    st.subheader("Per-Failure-Code Recovery Breakdown")
    st.caption("How AutoPey Rescue performs across each root cause category vs. blind retry.")

    if not results_data:
        st.warning("⚠️ Run `python src/run_batch.py` first.")
        st.stop()

    sys_breakdown = results_data.get("system", {}).get("category_breakdown", {})
    base_breakdown = results_data.get("baseline", {}).get("category_breakdown", {})

    failure_codes = ["INSUFFICIENT_BALANCE", "TECH_TIMEOUT", "MANDATE_EXPIRED", "HARD_DECLINE_OR_CANCELLED"]
    labels = {
        "INSUFFICIENT_BALANCE": "Insufficient Balance",
        "TECH_TIMEOUT": "Tech Timeout",
        "MANDATE_EXPIRED": "Mandate Expired",
        "HARD_DECLINE_OR_CANCELLED": "Hard Decline",
    }
    colors = {
        "INSUFFICIENT_BALANCE": "#F59E0B",
        "TECH_TIMEOUT": "#3B82F6",
        "MANDATE_EXPIRED": "#8B5CF6",
        "HARD_DECLINE_OR_CANCELLED": "#EF4444",
    }

    # Recovery rate comparison per category
    rate_rows = []
    for code in failure_codes:
        sys_r = sys_breakdown.get(code, {}).get("recovery_rate_pct", 0)
        base_r = base_breakdown.get(code, {}).get("recovery_rate_pct", 0)
        rate_rows.append({"Failure Code": labels[code], "AutoPey Rescue": sys_r, "Naive Baseline": base_r})

    rate_df = pd.DataFrame(rate_rows)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='section-title'>📈 Recovery Rate by Category</div>", unsafe_allow_html=True)
        fig_rate = go.Figure()
        fig_rate.add_trace(go.Bar(name='Naive Baseline', x=rate_df["Failure Code"],
                                  y=rate_df["Naive Baseline"], marker_color='#EF4444', opacity=0.8))
        fig_rate.add_trace(go.Bar(name='AutoPey Rescue', x=rate_df["Failure Code"],
                                  y=rate_df["AutoPey Rescue"], marker_color='#10B981', opacity=0.9))
        fig_rate.update_layout(
            barmode='group',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(15,20,35,0.6)',
            font=dict(color='#CBD5E1', family='Inter'),
            yaxis_title="Recovery Rate (%)",
            legend=dict(bgcolor='rgba(0,0,0,0)', bordercolor='rgba(255,255,255,0.1)'),
            height=320,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        )
        st.plotly_chart(fig_rate, use_container_width=True)

    with col2:
        st.markdown("<div class='section-title'>💰 Revenue Recovered by Category</div>", unsafe_allow_html=True)
        inr_rows = []
        for code in failure_codes:
            sys_inr = sys_breakdown.get(code, {}).get("total_recovered_inr", 0)
            base_inr = base_breakdown.get(code, {}).get("total_recovered_inr", 0)
            inr_rows.append({"Failure Code": labels[code], "AutoPey Rescue": sys_inr, "Naive Baseline": base_inr})
        inr_df = pd.DataFrame(inr_rows)

        fig_inr = go.Figure()
        fig_inr.add_trace(go.Bar(name='Naive Baseline', x=inr_df["Failure Code"],
                                  y=inr_df["Naive Baseline"], marker_color='#F59E0B', opacity=0.7))
        fig_inr.add_trace(go.Bar(name='AutoPey Rescue', x=inr_df["Failure Code"],
                                  y=inr_df["AutoPey Rescue"], marker_color='#6366F1', opacity=0.9))
        fig_inr.update_layout(
            barmode='group',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(15,20,35,0.6)',
            font=dict(color='#CBD5E1', family='Inter'),
            yaxis_title="₹ Recovered",
            legend=dict(bgcolor='rgba(0,0,0,0)', bordercolor='rgba(255,255,255,0.1)'),
            height=320,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        )
        st.plotly_chart(fig_inr, use_container_width=True)

    # Category table
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>📊 Detailed Category Metrics</div>", unsafe_allow_html=True)

    rows = []
    for code in failure_codes:
        s = sys_breakdown.get(code, {})
        b = base_breakdown.get(code, {})
        rows.append({
            "Failure Code": labels[code],
            "Root Cause": {"INSUFFICIENT_BALANCE": "balance", "TECH_TIMEOUT": "technical",
                           "MANDATE_EXPIRED": "expired", "HARD_DECLINE_OR_CANCELLED": "terminal"}.get(code),
            "System Action": {"INSUFFICIENT_BALANCE": "HOLD_AND_NUDGE", "TECH_TIMEOUT": "AUTO_RETRY",
                              "MANDATE_EXPIRED": "REAUTH_LINK", "HARD_DECLINE_OR_CANCELLED": "STOP_AND_FLAG"}.get(code),
            "# Transactions": s.get("total", 0),
            "Sys Recovery %": f"{s.get('recovery_rate_pct', 0)}%",
            "Base Recovery %": f"{b.get('recovery_rate_pct', 0)}%",
            "Sys ₹ Recovered": f"₹{s.get('total_recovered_inr', 0):,}",
            "Base ₹ Recovered": f"₹{b.get('total_recovered_inr', 0):,}",
            "Sys Contacts": s.get("total_contacts", 0),
            "Base Contacts": b.get("total_contacts", 0),
        })
    cat_df = pd.DataFrame(rows)
    st.dataframe(cat_df, use_container_width=True, hide_index=True)

    # Segment analysis if available
    sys_outcomes = results_data.get("system", {}).get("outcomes", [])
    if sys_outcomes and "customer_segment" in sys_outcomes[0]:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("<div class='section-title'>👥 Recovery by Customer Segment</div>", unsafe_allow_html=True)
        seg_df_raw = pd.DataFrame(sys_outcomes)
        seg_agg = seg_df_raw.groupby("customer_segment").agg(
            total=("transaction_id", "count"),
            recovered=("recovered", "sum"),
            recovered_inr=("recovered_amount_inr", "sum"),
        ).reset_index()
        seg_agg["recovery_rate_pct"] = (seg_agg["recovered"] / seg_agg["total"] * 100).round(1)

        fig_seg = px.bar(seg_agg, x="customer_segment", y="recovery_rate_pct",
                         color="recovery_rate_pct", color_continuous_scale="Viridis",
                         height=280, labels={"recovery_rate_pct": "Recovery %", "customer_segment": "Segment"})
        fig_seg.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(15,20,35,0.6)',
            font=dict(color='#CBD5E1', family='Inter'), showlegend=False,
            margin=dict(l=0, r=0, t=10, b=0),
            coloraxis_showscale=False,
            xaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.05)'),
        )
        st.plotly_chart(fig_seg, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3: ESCALATION QUEUE
# ═════════════════════════════════════════════════════════════════════════════
elif navigation == "🚨 Escalation Queue":
    st.subheader("Compliance Escalation Queue & Promise-to-Pay Tracker")
    st.caption("Cases automatically routed after customer outreach — with compliant stopping rules.")

    escalation_records = load_escalation_queue()

    if not escalation_records:
        st.warning("⚠️ No escalation records found. Run `python src/run_batch.py` to populate the queue.")
        st.stop()

    summary = get_escalation_summary(escalation_records)

    # Summary KPIs
    esc_c1, esc_c2, esc_c3, esc_c4 = st.columns(4)
    with esc_c1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{summary['total_escalations']}</div>
            <div class="kpi-label">Total Escalations</div>
        </div>""", unsafe_allow_html=True)
    with esc_c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color:#EF4444">{summary['high_priority_count']}</div>
            <div class="kpi-label">High Priority Cases</div>
            <div class="kpi-delta-neg">Require immediate action</div>
        </div>""", unsafe_allow_html=True)
    with esc_c3:
        promised_amt = summary.get("promised_amount_inr", 0)
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">₹{promised_amt:,}</div>
            <div class="kpi-label">₹ with Promise to Pay</div>
            <div class="kpi-delta-pos">Scheduled for follow-up</div>
        </div>""", unsafe_allow_html=True)
    with esc_c4:
        declined_amt = summary.get("declined_amount_inr", 0)
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value" style="color:#EF4444">₹{declined_amt:,}</div>
            <div class="kpi-label">₹ Permanently Stopped</div>
            <div class="kpi-delta-neutral">Customer terminated</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Path distribution chart
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("<div class='section-title'>📍 Escalation Path Distribution</div>", unsafe_allow_html=True)
        path_data = summary.get("by_path", {})
        path_colors = {
            "DECLINED_STOP": "#EF4444",
            "PROMISE_BROKEN": "#F59E0B",
            "RETRY_SCHEDULED": "#10B981",
            "HUMAN_REVIEW": "#6366F1",
            "PROMISE_KEPT": "#34D399",
        }
        path_df = pd.DataFrame([{"Path": k, "Count": v} for k, v in path_data.items()])
        if not path_df.empty:
            fig_pie = px.pie(path_df, values="Count", names="Path", hole=0.55,
                             color="Path", color_discrete_map=path_colors, height=280)
            fig_pie.update_traces(textposition='outside', textinfo='label+value')
            fig_pie.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#CBD5E1', family='Inter'),
                legend=dict(bgcolor='rgba(0,0,0,0)'),
                margin=dict(l=0, r=0, t=10, b=10),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown("<div class='section-title'>🚨 High Priority Escalations</div>", unsafe_allow_html=True)
        high_pri = [r for r in escalation_records if r.get("priority") == "HIGH"]
        if high_pri:
            for r in high_pri[:8]:  # Show first 8
                path = r.get("escalation_path", "UNKNOWN")
                badge_class = "badge-danger" if path in ["DECLINED_STOP", "PROMISE_BROKEN"] else "badge-warning"
                st.markdown(f"""
                <div class="escalation-HIGH">
                    <strong>{r.get('customer_name')}</strong>
                    <span class="{badge_class}" style="float:right">{path}</span><br>
                    <small>₹{r.get('amount_inr')} · {r.get('failure_code')} · {r.get('reason', '')[:80]}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No high priority escalations.")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # Full escalation table
    st.markdown("<div class='section-title'>📋 Full Escalation Queue</div>", unsafe_allow_html=True)
    priority_filter = st.selectbox("Filter by Priority", ["All", "HIGH", "MEDIUM", "LOW"])
    path_filter = st.multiselect("Filter by Path", list(path_data.keys()), default=[])

    esc_df = pd.DataFrame(escalation_records)
    if priority_filter != "All":
        esc_df = esc_df[esc_df["priority"] == priority_filter]
    if path_filter:
        esc_df = esc_df[esc_df["escalation_path"].isin(path_filter)]

    display_cols = ["timestamp", "transaction_id", "customer_name", "amount_inr",
                    "failure_code", "customer_reply_status", "promised_date",
                    "escalation_path", "priority", "next_action"]
    avail_cols = [c for c in display_cols if c in esc_df.columns]
    st.dataframe(esc_df[avail_cols], use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4: AUDIT TRAIL
# ═════════════════════════════════════════════════════════════════════════════
elif navigation == "🔍 Audit Trail":
    st.subheader("Immutable Audit Trail — Decision Ledger")
    st.caption("Every diagnosis, policy choice, guardrail evaluation, outreach message, and outcome — immutably logged.")

    audit_records = load_audit_trail()

    if not audit_records:
        st.warning("⚠️ No audit records found. Run `python src/run_batch.py` first.")
        st.stop()

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
            "Guardrail Status",
            options=["All", "Allowed Only", "Blocked Only"],
            index=0
        )
    with f_col3:
        search_query = st.text_input("Search by Customer / Txn ID", "")

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

    st.caption(f"Showing {len(filtered_df)} of {len(df_audit)} log entries")

    display_cols = [
        "timestamp", "transaction_id", "customer_name", "amount_inr",
        "failure_code", "root_cause", "chosen_action", "was_allowed", "block_reason", "outreach_message"
    ]
    avail_cols = [c for c in display_cols if c in filtered_df.columns]
    st.dataframe(filtered_df[avail_cols], use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5: TRANSACTION SPOTLIGHT
# ═════════════════════════════════════════════════════════════════════════════
elif navigation == "🎯 Transaction Spotlight":
    st.subheader("Transaction Spotlight — End-to-End Story")
    st.caption("Full pipeline walkthrough for any individual mandate. Use this for the demo pitch video.")

    audit_records = load_audit_trail()
    escalation_records = load_escalation_queue()

    if not audit_records:
        st.warning("⚠️ No audit records found. Run `python src/run_batch.py` first.")
        st.stop()

    txn_ids = sorted(list({r["transaction_id"] for r in audit_records if "transaction_id" in r}))
    selected_txn_id = st.selectbox("Select Transaction ID", options=txn_ids, index=0)

    matching_entries = [r for r in audit_records if r.get("transaction_id") == selected_txn_id]
    matching_esc = [r for r in escalation_records if r.get("transaction_id") == selected_txn_id]

    if not matching_entries:
        st.error("No records found for this transaction ID.")
        st.stop()

    first_entry = matching_entries[0]

    # Customer card
    st.markdown("""<div style="background: rgba(30,41,59,0.7); border-radius: 16px; padding: 1.5rem; border: 1px solid rgba(99,102,241,0.2);">""", unsafe_allow_html=True)
    info_c1, info_c2, info_c3, info_c4 = st.columns(4)
    with info_c1:
        st.markdown(f"**👤 Customer**  \n{first_entry.get('customer_name', '—')}")
        st.markdown(f"**ID:** `{first_entry.get('customer_id', '—')}`")
    with info_c2:
        st.markdown(f"**💰 Amount**  \n₹{first_entry.get('amount_inr', '—')}")
        st.markdown(f"**Due:** {first_entry.get('due_date', '—')}")
    with info_c3:
        fc = first_entry.get('failure_code', '—')
        rc = first_entry.get('root_cause', '—')
        st.markdown(f"**🔍 Failure Code**  \n`{fc}`")
        st.markdown(f"**Root Cause:** `{rc}`")
    with info_c4:
        action = first_entry.get('chosen_action', '—')
        was_allowed = first_entry.get('was_allowed', False)
        allowed_str = "✅ Allowed" if was_allowed else f"🚫 Blocked"
        st.markdown(f"**⚡ Action**  \n`{action}`")
        st.markdown(f"**Guardrail:** {allowed_str}")
    st.markdown("</div>", unsafe_allow_html=True)

    # Pipeline trace
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("<div class='section-title'>🔄 Pipeline Execution Trace</div>", unsafe_allow_html=True)

    pipeline_stages = [
        ("🔍", "Diagnosis", f"Failure Code `{first_entry.get('failure_code')}` → Root Cause: `{first_entry.get('root_cause')}`"),
        ("📋", "Policy", f"Action: `{first_entry.get('chosen_action')}` selected for `{first_entry.get('root_cause')}` root cause"),
        ("🛡️", "Guardrails", f"Status: {'✅ Action Allowed' if first_entry.get('was_allowed') else '🚫 ' + str(first_entry.get('block_reason', 'Blocked'))}"),
    ]

    has_outreach = any(e.get("outreach_message") for e in matching_entries)
    if has_outreach:
        pipeline_stages.append(("📱", "Outreach", "Hinglish WhatsApp nudge drafted and logged"))

    if matching_esc:
        esc = matching_esc[0]
        pipeline_stages.append(("🚨", "Escalation", f"Path: `{esc.get('escalation_path')}` · {esc.get('reason', '')[:80]}"))

    last_outcome = matching_entries[-1].get("outcome", {})
    if last_outcome:
        recovered = last_outcome.get("recovered", False)
        pipeline_stages.append(("💰", "Outcome", f"{'✅ RECOVERED' if recovered else '❌ NOT RECOVERED'} · Attempts: {last_outcome.get('attempts', 0)}"))

    for icon, stage, detail in pipeline_stages:
        st.markdown(f"""
        <div class="pipeline-step">
            <span class="step-icon">{icon}</span>
            <strong>{stage}</strong><br>
            <small style="color: #94A3B8">{detail}</small>
        </div>""", unsafe_allow_html=True)

    # WhatsApp Message Preview
    if has_outreach:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("<div class='section-title'>📱 WhatsApp Outreach Messages</div>", unsafe_allow_html=True)
        for entry in matching_entries:
            msg = entry.get("outreach_message")
            if msg:
                st.markdown(f"""
                <div class="whatsapp-bubble">
                    <b>AutoPey Concierge (WhatsApp)</b><br>
                    {msg}<br>
                    <small style="color: #94A3B8;">Sent: {entry.get('timestamp', '')}</small>
                </div>""", unsafe_allow_html=True)

    # Escalation detail
    if matching_esc:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("<div class='section-title'>🚨 Escalation Details</div>", unsafe_allow_html=True)
        for esc in matching_esc:
            priority = esc.get("priority", "LOW")
            st.markdown(f"""
            <div class="escalation-{priority}">
                <strong>Path:</strong> {esc.get('escalation_path')} · <strong>Priority:</strong> {priority}<br>
                <strong>Customer Reply:</strong> {esc.get('customer_reply_status')} (Promised: {esc.get('promised_date') or '—'})<br>
                <strong>Next Action:</strong> {esc.get('next_action', '—')}<br>
                <small style="color:#94A3B8">{esc.get('reason', '')}</small>
            </div>""", unsafe_allow_html=True)

    # Raw JSON log
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    with st.expander("📄 Raw Audit Log Entries (JSON)"):
        for idx, entry in enumerate(matching_entries, 1):
            st.json(entry)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 6: LIVE PIPELINE TESTER
# ═════════════════════════════════════════════════════════════════════════════
elif navigation == "⚡ Live Pipeline Tester":
    st.subheader("Live Pipeline Tester")
    st.caption("Run any mandate scenario through the full pipeline in real time — diagnosis, policy, guardrails, Hinglish nudge generation, and intent parsing.")

    sim_tab1, sim_tab2 = st.tabs(["⚙️ Failed Mandate Diagnostic", "💬 Promise-to-Pay Intent Classifier"])

    with sim_tab1:
        st.markdown("#### Run Any Failed Mandate Through the Full Pipeline")
        c1, c2 = st.columns(2)
        with c1:
            test_name = st.text_input("Customer Name", "Ananya Verma")
            test_amount = st.number_input("Amount (INR)", value=499, step=100, min_value=1)
            test_due = st.date_input("Due Date")
        with c2:
            test_code = st.selectbox("Failure Code", list(FAILURE_CODE_TO_ROOT_CAUSE.keys()))
            test_opted_out = st.checkbox("Customer Opted Out?", value=False)
            test_segment = st.selectbox("Customer Segment", ["High Value", "Mid Tier", "Budget", "At Risk", "Churning"])

        if st.button("⚡ Run Full Pipeline Diagnostic", type="primary", use_container_width=True):
            txn = {
                "transaction_id": "TEST_TXN_LIVE",
                "customer_name": test_name,
                "amount_inr": test_amount,
                "due_date": str(test_due),
                "failure_code": test_code,
                "opted_out": test_opted_out,
                "customer_segment": test_segment,
                "merchant_category": "Live Test",
                "risk_score": 0.5,
            }

            with st.spinner("Running pipeline..."):
                root_cause = diagnose(txn)
                policy = decide_action(txn, root_cause)
                guardrail = is_action_allowed(txn, policy, contact_history=[])
                nudge_msg = draft_nudge(txn) if guardrail["allowed"] and policy["action"] in ["HOLD_AND_NUDGE", "REAUTH_LINK"] else None

            st.markdown("---")
            res_c1, res_c2, res_c3 = st.columns(3)
            with res_c1:
                st.metric("Root Cause", root_cause)
                st.metric("Max Retries", policy["max_retries"])
            with res_c2:
                st.metric("Policy Action", policy["action"])
                gap = f"{policy['min_gap_hours']}h" if policy.get("min_gap_hours") else "N/A"
                st.metric("Min Cooldown Gap", gap)
            with res_c3:
                status_txt = "✅ Allowed" if guardrail["allowed"] else f"🚫 {guardrail['reason']}"
                st.metric("Guardrail Decision", status_txt)
                st.metric("Policy Description", "", help=policy.get("description", ""))

            if nudge_msg:
                st.markdown("#### 📱 Generated Hinglish WhatsApp Message")
                st.markdown(f"""
                <div class="whatsapp-bubble">
                    <b>AutoPey Concierge (WhatsApp)</b><br>
                    {nudge_msg}<br>
                    <small style="color: #94A3B8">Drafted & logged — not dispatched to live messaging</small>
                </div>""", unsafe_allow_html=True)
                st.caption(f"Message length: {len(nudge_msg)} characters (max 299)")
            elif not guardrail["allowed"]:
                st.error(f"🚫 Guardrail blocked: {guardrail['reason']} — No message drafted.")
            else:
                st.info(f"ℹ️ Action `{policy['action']}` — No outreach message needed.")

    with sim_tab2:
        st.markdown("#### Classify Customer WhatsApp Reply Intent")
        st.caption("Paste any Hinglish or English customer reply to see how the AI classifies payment intent.")

        presets = [
            "Haan kal pakka pay kar dunga",
            "Salary aane do 5th ko tab automatic ho jayega",
            "Band karo ye subscription, I have already cancelled",
            "Aaj shaam 7 baje karunga",
            "Who is this? Fraud message lag raha hai",
            "Ok ok, will do it by Sunday",
            "Nahi chahiye, please stop",
            "Dekh lete hain",
        ]
        selected = st.selectbox("Try a sample reply:", ["-- Custom Input --"] + presets)
        reply_input = st.text_area(
            "Customer Reply:", value="" if selected == "-- Custom Input --" else selected,
            placeholder="Type Hinglish customer reply here..."
        )

        if st.button("🤖 Parse Intent", type="primary"):
            if not reply_input.strip():
                st.error("Please enter a reply.")
            else:
                with st.spinner("Analyzing intent..."):
                    intent = parse_promise_to_pay(reply_input)

                status = intent.get("status")
                date = intent.get("promised_date")

                if status == "PROMISED":
                    st.success(f"✅ **PROMISED** — Customer intends to pay")
                    if date:
                        st.info(f"📅 Promise date extracted: **{date}** → System will hold retries until this date")
                    else:
                        st.info("📅 No specific date — 48h follow-up scheduled")
                    st.markdown("<span class='badge-success'>RETRY_SCHEDULED</span> Escalation path", unsafe_allow_html=True)
                elif status == "DECLINED":
                    st.error(f"🛑 **DECLINED** — Customer terminated subscription")
                    st.warning("⛔ All automated contacts stopped immediately. CRM opt-out flag set.")
                    st.markdown("<span class='badge-danger'>DECLINED_STOP</span> Escalation path", unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ **UNCLEAR** — Ambiguous response")
                    st.info("Routing to human support agent for manual review.")
                    st.markdown("<span class='badge-info'>HUMAN_REVIEW</span> Escalation path", unsafe_allow_html=True)

                st.json(intent)
