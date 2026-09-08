import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as gg
import datetime
import uuid

from app.database import SessionLocal, engine, Base
from app.models import Link, Policy, Organisation, Application, FlowRecord, AuditLog
from app.policy_engine import PolicyEngine, PolicyEngineConfig
from app.fallback import FallbackEngine
from app.classifier import ApplicationClassifier, DEFAULT_APP_CLASSES
from app.simulator import CongestionSimulator
from app.permissions import PermissionChecker, UserContext
from experiments.run_experiment import ExperimentRunner

# Page Configuration
st.set_page_config(
    page_title="HybridFlowGuard – Bandwidth Policy Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark Glassmorphism UI)
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    .header-banner {
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border-left: 5px solid #3b82f6;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .status-healthy {
        color: #10b981;
        font-weight: bold;
    }
    .status-degraded {
        color: #f59e0b;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Helper: Get DB Session
def get_db():
    return SessionLocal()

# Header Banner
st.markdown("""
<div class="header-banner">
    <h2 style="margin:0; color:#f9fafb;">⚡ HybridFlowGuard Policy Control Center</h2>
    <p style="margin:4px 0 0 0; color:#9ca3af; font-size: 14px;">
        Application-Aware Bandwidth Allocation, Multi-Tenant Isolation & Telemetry Fallback Engine
    </p>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration & User Role Context
st.sidebar.title("👤 User Context & Role (RBAC)")

user_role = st.sidebar.selectbox(
    "Select User Role:",
    ["admin", "network_manager", "organisation_manager", "external_partner", "viewer"],
    index=0
)

user_org = st.sidebar.selectbox(
    "Assigned Organisation:",
    ["org_chennai_hq", "org_bangalore_hub", "org_mumbai_hub", "org_aws_cloud", "org_azure_cloud", "org_remote_work", "org_external_partner"],
    index=0
)

current_user = UserContext(
    user_id="usr_dash_1",
    username=f"user_{user_role}",
    organisation_id=user_org,
    role=user_role
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation")
menu = st.sidebar.radio(
    "Choose View:",
    ["🌐 Link Topology & Infrastructure", "🧪 Policy Sandbox & Simulator", "🔐 Multi-Tenant Policy Manager", "🛡️ Telemetry Fallback Monitor", "📊 Baseline vs HybridFlowGuard Benchmarks"]
)

db = get_db()

# VIEW 1: LINK TOPOLOGY & INFRASTRUCTURE
if menu == "🌐 Link Topology & Infrastructure":
    st.subheader("🌐 Network Link Infrastructure & Telemetry Status")
    
    links = db.query(Link).all()
    if not links:
        st.warning("No link infrastructure seeded in database.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        total_links = len(links)
        avg_util = np.mean([l.utilisation_pct or 0 for l in links])
        congested_links = len([l for l in links if (l.utilisation_pct or 0) >= 85.0])
        stale_status = FallbackEngine.evaluate_flow_freshness(datetime.datetime.utcnow())[0]

        col1.metric("Total Links Monitored", total_links)
        col2.metric("Avg Link Utilisation", f"{avg_util:.1f}%")
        col3.metric("Congested Links (≥85%)", congested_links, delta_color="inverse")
        col4.metric("Telemetry Health", "Operational" if not stale_status else "Degraded", delta_color="normal" if not stale_status else "inverse")

        st.markdown("### 📡 Live Link Capacity & Utilisation Gauges")
        
        cols = st.columns(3)
        for idx, l in enumerate(links):
            util = l.utilisation_pct or 0.0
            color = "#ef4444" if util >= 85.0 else ("#f59e0b" if util >= 70.0 else "#10b981")
            
            fig = gg.Figure(gg.Indicator(
                mode = "gauge+number",
                value = util,
                title = {'text': f"{l.name}<br><span style='font-size:0.8em;color:gray'>{l.source} → {l.destination} ({l.capacity_mbps} Mbps)</span>"},
                number = {'suffix': "%"},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 70], 'color': "rgba(16, 185, 129, 0.1)"},
                        {'range': [70, 85], 'color': "rgba(245, 158, 11, 0.1)"},
                        {'range': [85, 100], 'color': "rgba(239, 68, 68, 0.1)"}
                    ]
                }
            ))
            fig.update_layout(height=220, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            cols[idx % 3].plotly_chart(fig, use_container_width=True)

# VIEW 2: POLICY SANDBOX & SIMULATOR
elif menu == "🧪 Policy Sandbox & Simulator":
    st.subheader("🧪 Live Policy Engine Evaluation Sandbox")
    st.markdown("Test live bandwidth policy decisions under simulated traffic flows and dynamic link congestion levels.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### 1. Input Flow Parameters")
        sim_org = st.selectbox("Organisation ID", ["org_chennai_hq", "org_bangalore_hub", "org_mumbai_hub", "org_external_partner"])
        sim_app = st.selectbox("Application", list(DEFAULT_APP_CLASSES.keys()) + ["CustomUnknownApp"])
        sim_class = ApplicationClassifier.classify(sim_app, db=db)
        st.caption(f"Detected Class: **{sim_class}**")

        sim_util = st.slider("Simulated Link Utilisation (%)", 0.0, 100.0, 92.0, 0.5)
        sim_prio = st.slider("Service Priority Weight (1-100)", 1, 100, 90)
        sim_link = st.selectbox("Target Link", [l.id for l in db.query(Link).all()])

    with col2:
        st.markdown("#### 2. Policy Engine Decision Preview")
        engine_instance = PolicyEngine()
        
        req = PolicyEvalRequest(
            flow_id=f"sim_{uuid.uuid4().hex[:6]}",
            organisation_id=sim_org,
            application=sim_app,
            application_class=sim_class,
            link_id=sim_link,
            link_utilisation_pct=sim_util,
            service_priority=sim_prio
        )

        res = engine_instance.evaluate(req, db=db)

        # Decision Badge Styling
        dec_color = {
            "GUARANTEE_MINIMUM": "#10b981",
            "PRIORITISE": "#3b82f6",
            "RATE_LIMIT": "#ef4444",
            "NORMAL": "#6b7280"
        }.get(res.decision, "#6b7280")

        st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.03); border: 2px solid {dec_color}; border-radius: 10px; padding: 16px;">
            <h3 style="margin:0; color:{dec_color};">Action: {res.decision}</h3>
            <p style="margin: 8px 0 0 0; color:#e5e7eb;"><b>Calculated Priority Score:</b> {res.priority_score}</p>
            <p style="margin: 4px 0 0 0; color:#e5e7eb;"><b>Bandwidth Allocation:</b> Min: {res.minimum_bandwidth_mbps} Mbps | Max: {res.maximum_bandwidth_mbps} Mbps</p>
            <p style="margin: 12px 0 0 0; color:#9ca3af; font-size: 13px;"><b>Decision Reasoning:</b> {res.reason}</p>
        </div>
        """, unsafe_allow_html=True)

        if res.warning:
            st.warning(f"⚠️ Telemetry Alert: {res.warning}")

# VIEW 3: MULTI-TENANT POLICY MANAGER
elif menu == "🔐 Multi-Tenant Policy Manager":
    st.subheader("🔐 Multi-Tenant Bandwidth Policy Rules")
    st.info(f"Viewing policy records filtered by role **'{current_user.role}'** for org **'{current_user.organisation_id}'**.")

    all_policies = db.query(Policy).all()
    filtered_policies = PermissionChecker.filter_records_by_tenant(current_user, all_policies)

    pol_data = [{
        "ID": p.id,
        "Organisation": p.organisation_id,
        "Application": p.application or "ALL",
        "App Class": p.application_class,
        "Priority": p.priority,
        "Min Bandwidth (Mbps)": p.minimum_bandwidth_mbps,
        "Max Bandwidth (Mbps)": p.maximum_bandwidth_mbps,
        "Policy Action": p.action
    } for p in filtered_policies]

    st.dataframe(pd.DataFrame(pol_data), use_container_width=True)

    # Policy Creation Section (RBAC Check)
    st.markdown("### ➕ Create New Tenant Policy Rule")
    if current_user.role in ["viewer", "external_partner"]:
        st.warning("⚠️ Write operations restricted for Viewer / External Partner roles.")
    else:
        with st.form("create_policy_form"):
            c1, c2, c3 = st.columns(3)
            new_org = c1.text_input("Organisation ID", value=current_user.organisation_id if current_user.role == "organisation_manager" else "org_chennai_hq")
            new_app = c2.text_input("Application Name (Optional)", value="")
            new_class = c3.selectbox("Application Class", ["Critical", "Important", "Normal", "Non-critical"])

            c4, c5, c6 = st.columns(3)
            new_prio = c4.number_input("Priority Weight", 1, 100, 80)
            new_min_bw = c5.number_input("Min Bandwidth (Mbps)", 0.0, 100.0, 30.0)
            new_max_bw = c6.number_input("Max Bandwidth (Mbps)", 0.0, 100.0, 100.0)

            new_action = st.selectbox("Policy Action", ["PRIORITISE", "GUARANTEE_MINIMUM", "RATE_LIMIT", "NORMAL"])
            submitted = st.form_submit_button("Create Policy Rule")

            if submitted:
                try:
                    PermissionChecker.validate_role_for_write(current_user)
                    PermissionChecker.enforce_tenant_isolation(current_user, new_org)
                    new_id = f"pol_{uuid.uuid4().hex[:8]}"
                    p_obj = Policy(
                        id=new_id,
                        organisation_id=new_org,
                        application=new_app if new_app.strip() else None,
                        application_class=new_class,
                        priority=new_prio,
                        minimum_bandwidth_mbps=new_min_bw,
                        maximum_bandwidth_mbps=new_max_bw,
                        action=new_action
                    )
                    db.add(p_obj)
                    db.commit()
                    st.success(f"Successfully created policy rule '{new_id}'!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to create policy: {str(e)}")

# VIEW 4: TELEMETRY FALLBACK MONITOR
elif menu == "🛡️ Telemetry Fallback Monitor":
    st.subheader("🛡️ Telemetry Health & Edge Fallback Engine")
    st.markdown("Monitors system resilience against missing metrics, delayed flow telemetry, or unclassified applications.")

    stale_flow, flow_msg = FallbackEngine.evaluate_flow_freshness(datetime.datetime.utcnow())
    links_missing = db.query(Link).filter((Link.utilisation_pct == None) | (Link.utilisation_pct < 0)).count()

    c1, c2, c3 = st.columns(3)
    c1.metric("Flow Telemetry Freshness", "Stale" if stale_flow else "Fresh", delta_color="normal" if not stale_flow else "inverse")
    c2.metric("Missing Link Metrics", links_missing, delta_color="normal" if links_missing == 0 else "inverse")
    c3.metric("Fallback Action Mode", "Active" if (stale_flow or links_missing > 0) else "Standby")

    st.markdown("### 🧪 Telemetry Fault Injection Simulator")
    sim_fault = st.radio("Simulate Fault Condition:", ["None (Healthy Telemetry)", "Stale Timestamp (>30s)", "Corrupted/Missing Link Metric", "Unclassified Application"])

    if sim_fault == "Stale Timestamp (>30s)":
        stale_ts = datetime.datetime.utcnow() - datetime.timedelta(seconds=45)
        stale, msg = FallbackEngine.evaluate_flow_freshness(stale_ts)
        st.warning(f"⚠️ {msg}")
    elif sim_fault == "Corrupted/Missing Link Metric":
        val, stale, msg = FallbackEngine.resolve_link_utilisation("link_missing_sim", None, db=db)
        st.warning(f"⚠️ {msg} (Resolved Utilisation: {val}%)")
    elif sim_fault == "Unclassified Application":
        cls, act, msg = FallbackEngine.resolve_unknown_application("ShadowApp99", "UNKNOWN")
        st.warning(f"⚠️ {msg}")

# VIEW 5: BASELINE VS HYBRIDFLOWGUARD BENCHMARKS
elif menu == "📊 Baseline vs HybridFlowGuard Benchmarks":
    st.subheader("📊 Baseline (FIFO) vs HybridFlowGuard Benchmark Experiments")
    st.markdown("Compare empirical network performance metrics under high congestion scenarios.")

    col_ctrl, col_chart = st.columns([1, 2])

    with col_ctrl:
        st.markdown("#### Experiment Parameters")
        scenario_select = st.selectbox("Congestion Scenario", ["90% congestion", "98% congestion", "Normal network"])
        num_flows_select = st.slider("Simulated Flow Volume", 100, 1000, 300, 50)
        
        if st.button("🚀 Run Reproducible Benchmark Experiment"):
            with st.spinner("Executing experiment flow evaluation..."):
                exp_res = ExperimentRunner.run(scenario=scenario_select, num_flows=num_flows_select)
                st.session_state["exp_res"] = exp_res

    if "exp_res" in st.session_state:
        res = st.session_state["exp_res"]

        with col_chart:
            st.markdown(f"#### Performance Comparison ({res['scenario']})")
            
            metrics_df = pd.DataFrame(res["metrics_summary"])
            
            # Plotly Throughput Chart
            fig = px.bar(
                metrics_df,
                x="metric",
                y=["baseline", "hybridflowguard"],
                barmode="group",
                title="Baseline vs HybridFlowGuard Performance Comparison",
                labels={"value": "Metric Value", "metric": "Key Performance Metric"},
                color_discrete_sequence=["#ef4444", "#10b981"]
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, height=360)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 📝 Automated Empirical Analysis Report")
        st.markdown(res["error_analysis"])

db.close()
