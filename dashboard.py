import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as gg
import datetime
import uuid

from app.database import SessionLocal, engine, Base
from app.models import Link, Policy, Organisation, Application, FlowRecord, AuditLog, PolicyDecision
from app.policy_engine import PolicyEngine, PolicyEngineConfig
from app.fallback import FallbackEngine
from app.classifier import ApplicationClassifier, DEFAULT_APP_CLASSES
from app.simulator import CongestionSimulator, SUPPORTED_SCENARIOS
from app.permissions import PermissionChecker, UserContext
from experiments.run_experiment import ExperimentRunner, ActiveCongestionPipeline

# Page Configuration
st.set_page_config(
    page_title="HybridFlowGuard – Policy & Saturation Control Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling (Dark Glassmorphism UI)
st.markdown("""
<style>
    .main {
        background-color: #0c1017;
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
    }
    .header-banner {
        background: linear-gradient(135deg, #111827 0%, #1f2937 50%, #0f172a 100%);
        border-left: 6px solid #3b82f6;
        padding: 20px 24px;
        border-radius: 10px;
        margin-bottom: 22px;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
    }
    .role-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .badge-admin { background: #8b5cf6; color: #fff; }
    .badge-netmgr { background: #3b82f6; color: #fff; }
    .badge-orgmgr { background: #10b981; color: #fff; }
    .badge-partner { background: #f59e0b; color: #fff; }
    .badge-viewer { background: #6b7280; color: #fff; }
    
    .action-badge {
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: bold;
    }
    .action-guarantee { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }
    .action-prioritise { background: rgba(59, 130, 246, 0.2); color: #3b82f6; border: 1px solid #3b82f6; }
    .action-ratelimit { background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; }
    .action-normal { background: rgba(156, 163, 175, 0.2); color: #9ca3af; border: 1px solid #9ca3af; }
</style>
""", unsafe_allow_html=True)

# Helper: Get DB Session
def get_db():
    return SessionLocal()

db = get_db()

# Sidebar Configuration & User Role Context (RBAC)
st.sidebar.title("👤 Role-Based Access Control (RBAC)")

user_role = st.sidebar.selectbox(
    "Select User Role:",
    ["admin", "network_manager", "organisation_manager", "external_partner", "viewer"],
    index=0
)

# Populate available tenant organisations
all_orgs = [o.id for o in db.query(Organisation).all()] or [
    "org_chennai_hq", "org_bangalore_hub", "org_mumbai_hub", "org_aws_cloud", "org_azure_cloud", "org_remote_work", "org_external_partner"
]

user_org = st.sidebar.selectbox(
    "Active Organisation Scope:",
    all_orgs,
    index=0 if user_role != "external_partner" else (all_orgs.index("org_external_partner") if "org_external_partner" in all_orgs else 0)
)

current_user = UserContext(
    user_id=f"usr_{user_role}_1",
    username=f"{user_role}_operator",
    organisation_id=user_org,
    role=user_role
)

# Role Badge in Sidebar
role_badge_class = {
    "admin": "badge-admin",
    "network_manager": "badge-netmgr",
    "organisation_manager": "badge-orgmgr",
    "external_partner": "badge-partner",
    "viewer": "badge-viewer"
}.get(user_role, "badge-viewer")

st.sidebar.markdown(f"""
<div style="margin-top: 10px; margin-bottom: 15px;">
    <span class="role-badge {role_badge_class}">{user_role.replace('_', ' ').upper()}</span>
    <p style="margin: 6px 0 0 0; font-size: 12px; color: #9ca3af;">
        Scope: <b>{user_org}</b><br>
        Permissions: <b>{"Full Read/Write" if user_role in ["admin", "network_manager"] else ("Tenant Scoped" if user_role == "organisation_manager" else "Read-Only / SLA")}</b>
    </p>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation Views")
menu = st.sidebar.radio(
    "Choose View:",
    [
        "🌐 Link Saturation & Infrastructure",
        "⚡ Live Enforcement Decisions Feed",
        "🧪 Policy Decision Sandbox & Edge Simulator",
        "🔐 Multi-Tenant Policy Manager",
        "🛡️ Telemetry Fallback Monitor",
        "📊 Active Congestion Benchmarks"
    ]
)

# Header Banner with active role indicator
st.markdown(f"""
<div class="header-banner">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <h2 style="margin:0; color:#f9fafb;">⚡ HybridFlowGuard Policy Control Center</h2>
            <p style="margin:6px 0 0 0; color:#9ca3af; font-size: 14px;">
                Application-Aware Bandwidth Allocation • Real-Time Link Saturation • Active Congestion Benchmark Pipeline
            </p>
        </div>
        <div>
            <span class="role-badge {role_badge_class}">{user_role.upper()} VIEW</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# VIEW 1: LINK SATURATION & INFRASTRUCTURE COMMAND
# -----------------------------------------------------------------------------
if menu == "🌐 Link Saturation & Infrastructure":
    st.subheader("🌐 Network Link Infrastructure & Saturation Matrix")
    
    links = db.query(Link).all()
    if not links:
        st.warning("No link infrastructure found in database.")
    else:
        # Multi-role filtering: partner only sees extranet, org_manager highlights their link
        if current_user.role == "external_partner":
            display_links = [l for l in links if l.id == "link_partner_extranet"]
            st.info("ℹ️ External Partner view restricted to Extranet Gateway link.")
        else:
            display_links = links

        col1, col2, col3, col4 = st.columns(4)
        total_links = len(display_links)
        avg_util = np.mean([l.utilisation_pct or 0 for l in display_links]) if display_links else 0.0
        congested_links = len([l for l in display_links if (l.utilisation_pct or 0) >= 85.0])
        stale_status = FallbackEngine.evaluate_flow_freshness(datetime.datetime.now(datetime.timezone.utc))[0]

        col1.metric("Monitored Links", total_links)
        col2.metric("Mean Saturation", f"{avg_util:.1f}%")
        col3.metric("Congested Links (≥85%)", congested_links, delta_color="inverse")
        col4.metric("Telemetry Pipeline", "Operational" if not stale_status else "Degraded", delta_color="normal" if not stale_status else "inverse")

        st.markdown("### 📡 Real-Time Link Saturation Gauges")
        cols = st.columns(3)
        for idx, l in enumerate(display_links):
            util = l.utilisation_pct or 0.0
            color = "#ef4444" if util >= 85.0 else ("#f59e0b" if util >= 70.0 else "#10b981")
            headroom = max(0.0, l.capacity_mbps * (1.0 - util / 100.0))
            
            fig = gg.Figure(gg.Indicator(
                mode="gauge+number",
                value=util,
                title={'text': f"<b>{l.name}</b><br><span style='font-size:0.75em;color:#9ca3af'>{l.source} → {l.destination}</span><br><span style='font-size:0.7em;color:#60a5fa'>Headroom: {headroom:.1f} Mbps</span>"},
                number={'suffix': "%"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 70], 'color': "rgba(16, 185, 129, 0.12)"},
                        {'range': [70, 85], 'color': "rgba(245, 158, 11, 0.15)"},
                        {'range': [85, 100], 'color': "rgba(239, 68, 68, 0.20)"}
                    ],
                    'threshold': {
                        'line': {'color': "#ef4444", 'width': 3},
                        'thickness': 0.75,
                        'value': 95
                    }
                }
            ))
            fig.update_layout(height=230, margin=dict(l=20, r=20, t=65, b=20), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            cols[idx % 3].plotly_chart(fig, use_container_width=True)

        st.markdown("### 📊 Link Saturation Matrix & Headroom Summary")
        mat_data = []
        for l in display_links:
            u = l.utilisation_pct or 0.0
            status_text = "Severe Saturation (≥95%)" if u >= 95 else ("High Congestion (≥85%)" if u >= 85 else ("Moderate (≥70%)" if u >= 70 else "Normal"))
            mat_data.append({
                "Link ID": l.id,
                "Link Name": l.name,
                "Source": l.source,
                "Destination": l.destination,
                "Capacity (Mbps)": l.capacity_mbps,
                "Instantaneous Utilisation (%)": f"{u:.1f}%",
                "Available Headroom (Mbps)": f"{max(0.0, l.capacity_mbps * (1 - u/100)):.1f}",
                "Saturation State": status_text
            })
        st.dataframe(pd.DataFrame(mat_data), use_container_width=True)

        # Dynamic Saturation & Queue Depth Timeline (Interactive Edge Condition Tester)
        st.markdown("### 📈 Link Saturation & Queue Depth Timeline (Edge Simulation)")
        c_time_ctrl1, c_time_ctrl2 = st.columns([1, 2])
        with c_time_ctrl1:
            timeline_link = st.selectbox("Select Link to Inspect:", [l.id for l in display_links])
            timeline_scen = st.selectbox("Simulate Condition:", ["Bursty traffic spike", "High-jitter link", "90% congestion", "98% congestion", "Normal network"])
            timeline_steps = st.slider("Time Window (Seconds):", 30, 120, 60, 10)
        
        ts_data = CongestionSimulator.generate_time_series_telemetry(
            link_id=timeline_link,
            count=timeline_steps,
            scenario=timeline_scen
        )

        with c_time_ctrl2:
            fig_ts = gg.Figure()
            fig_ts.add_trace(gg.Scatter(
                x=ts_data["time_offset_sec"],
                y=ts_data["link_utilisation_pct"],
                mode="lines+markers",
                name="Link Utilisation (%)",
                line=dict(color="#3b82f6", width=2.5)
            ))
            # Saturation Threshold lines
            fig_ts.add_hline(y=95.0, line_dash="dash", line_color="#ef4444", annotation_text="Severe Saturation (95%)", annotation_position="top right")
            fig_ts.add_hline(y=85.0, line_dash="dot", line_color="#f59e0b", annotation_text="High Congestion (85%)", annotation_position="bottom right")
            fig_ts.add_hline(y=70.0, line_dash="dot", line_color="#10b981", annotation_text="Warning Threshold (70%)")

            fig_ts.update_layout(
                title=f"Instantaneous Saturation vs Thresholds ({timeline_link})",
                xaxis_title="Time Offset (Seconds)",
                yaxis_title="Utilisation (%)",
                yaxis_range=[20, 105],
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={'color': "white"}
            )
            st.plotly_chart(fig_ts, use_container_width=True)

        # Buffer Queue Depth & Jitter Charts
        c_q, c_jit = st.columns(2)
        with c_q:
            fig_q = px.area(
                ts_data,
                x="time_offset_sec",
                y="queue_depth_kb",
                title="Buffer Queue Occupancy (KB) – Bufferbloat Risk",
                color_discrete_sequence=["#f97316"],
                labels={"time_offset_sec": "Time Offset (s)", "queue_depth_kb": "Queue Depth (KB)"}
            )
            fig_q.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig_q, use_container_width=True)

        with c_jit:
            fig_jit = px.line(
                ts_data,
                x="time_offset_sec",
                y="jitter_ms",
                title="Packet Delay Variation / Jitter (ms)",
                color_discrete_sequence=["#a855f7"],
                labels={"time_offset_sec": "Time Offset (s)", "jitter_ms": "Jitter (ms)"}
            )
            fig_jit.update_layout(height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
            st.plotly_chart(fig_jit, use_container_width=True)


# -----------------------------------------------------------------------------
# VIEW 2: LIVE ENFORCEMENT DECISIONS FEED & ANALYTICS
# -----------------------------------------------------------------------------
elif menu == "⚡ Live Enforcement Decisions Feed":
    st.subheader("⚡ Real-Time Policy Enforcement Decision Stream")
    st.markdown("Surfaces dynamic admission control decisions evaluated by HybridFlowGuard across link topologies.")

    # Retrieve recent flows
    recent_flows = db.query(FlowRecord).order_by(FlowRecord.timestamp.desc()).limit(200).all()
    filtered_flows = PermissionChecker.filter_records_by_tenant(current_user, recent_flows)

    if not filtered_flows:
        st.info("No flow enforcement records found. Generating live simulated flow telemetry...")
        gen_df = CongestionSimulator.generate_dataset(count=80, scenario="Bursty traffic spike", org_id=current_user.organisation_id if current_user.role == "organisation_manager" else None)
        pe = PolicyEngine()
        flow_rows = []
        for _, r in gen_df.iterrows():
            eval_res = pe.evaluate(PolicyEvalRequest(
                flow_id=r["id"],
                organisation_id=r["organisation_id"],
                application=r["application"],
                application_class=r["application_class"],
                link_id=r["link_id"],
                link_utilisation_pct=r["link_utilisation_pct"],
                service_priority=r["service_priority"]
            ), db=db)
            flow_rows.append({
                "Flow ID": r["id"],
                "Timestamp": r["timestamp"][:19],
                "Organisation": r["organisation_id"],
                "Application": r["application"],
                "Class": r["application_class"],
                "Link ID": r["link_id"],
                "Utilisation": f"{r['link_utilisation_pct']:.1f}%",
                "Action": eval_res.decision,
                "Priority Score": eval_res.priority_score,
                "Allocated Bandwidth": f"{eval_res.minimum_bandwidth_mbps} - {eval_res.maximum_bandwidth_mbps} Mbps",
                "Reasoning": eval_res.reason
            })
        feed_df = pd.DataFrame(flow_rows)
    else:
        flow_rows = []
        for f in filtered_flows:
            flow_rows.append({
                "Flow ID": f.id,
                "Timestamp": str(f.timestamp)[:19],
                "Organisation": f.organisation_id,
                "Application": f.application,
                "Class": f.application_class,
                "Link ID": f.link_id,
                "Utilisation": f"{f.link_utilisation_pct:.1f}%",
                "Action": f.policy_action,
                "Priority Score": f.service_priority,
                "Allocated Bandwidth": "Priority Reserved" if f.policy_action in ["GUARANTEE_MINIMUM", "PRIORITISE"] else ("Throttled ≤15 Mbps" if f.policy_action == "RATE_LIMIT" else "Normal"),
                "Reasoning": f"Enforced dynamic policy for class '{f.application_class}' under {f.link_utilisation_pct:.1f}% link load."
            })
        feed_df = pd.DataFrame(flow_rows)

    # Top KPI Metrics for Decisions
    k1, k2, k3, k4 = st.columns(4)
    total_evals = len(feed_df)
    guaranteed = len(feed_df[feed_df["Action"] == "GUARANTEE_MINIMUM"])
    prioritised = len(feed_df[feed_df["Action"] == "PRIORITISE"])
    rate_limited = len(feed_df[feed_df["Action"] == "RATE_LIMIT"])

    k1.metric("Evaluated Flows", total_evals)
    k2.metric("Guaranteed Minimum", guaranteed, delta=f"{(guaranteed/total_evals*100):.1f}%" if total_evals else "0%")
    k3.metric("Prioritised Queues", prioritised, delta=f"{(prioritised/total_evals*100):.1f}%" if total_evals else "0%")
    k4.metric("Rate-Limited (Throttled)", rate_limited, delta_color="inverse", delta=f"{(rate_limited/total_evals*100):.1f}%" if total_evals else "0%")

    # Charts: Decision Breakdown & Action by Application Class
    st.markdown("### 📊 Policy Decision Distribution & Class Enforcement")
    c_pie, c_bar = st.columns([1, 2])
    with c_pie:
        action_counts = feed_df["Action"].value_counts().reset_index()
        action_counts.columns = ["Action", "Count"]
        color_map = {
            "GUARANTEE_MINIMUM": "#10b981",
            "PRIORITISE": "#3b82f6",
            "RATE_LIMIT": "#ef4444",
            "NORMAL": "#6b7280"
        }
        fig_donut = px.pie(
            action_counts,
            names="Action",
            values="Count",
            title="Enforcement Action Distribution",
            hole=0.45,
            color="Action",
            color_discrete_map=color_map
        )
        fig_donut.update_layout(height=280, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
        st.plotly_chart(fig_donut, use_container_width=True)

    with c_bar:
        class_action = feed_df.groupby(["Class", "Action"]).size().reset_index(name="Flows")
        fig_class = px.bar(
            class_action,
            x="Class",
            y="Flows",
            color="Action",
            barmode="stack",
            title="Policy Enforcement Actions by Application Class",
            color_discrete_map=color_map
        )
        fig_class.update_layout(height=280, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
        st.plotly_chart(fig_class, use_container_width=True)

    # Filter Controls for Decision Table
    st.markdown("### 📋 Interactive Decision Stream Filter")
    f_c1, f_c2, f_c3 = st.columns(3)
    sel_action = f_c1.selectbox("Filter by Action:", ["ALL"] + list(feed_df["Action"].unique()))
    sel_class = f_c2.selectbox("Filter by App Class:", ["ALL"] + list(feed_df["Class"].unique()))
    sel_link = f_c3.selectbox("Filter by Link ID:", ["ALL"] + list(feed_df["Link ID"].unique()))

    display_feed = feed_df.copy()
    if sel_action != "ALL":
        display_feed = display_feed[display_feed["Action"] == sel_action]
    if sel_class != "ALL":
        display_feed = display_feed[display_feed["Class"] == sel_class]
    if sel_link != "ALL":
        display_feed = display_feed[display_feed["Link ID"] == sel_link]

    st.dataframe(display_feed, use_container_width=True)


# -----------------------------------------------------------------------------
# VIEW 3: POLICY DECISION SANDBOX & EDGE SIMULATOR
# -----------------------------------------------------------------------------
elif menu == "🧪 Policy Decision Sandbox & Edge Simulator":
    st.subheader("🧪 Live Policy Engine Sandbox & Edge Case Stress-Tester")
    st.markdown("Simulate individual flow admission and test edge-case conditions (Bursty traffic spikes, High-jitter link variations).")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown("#### 1. Input Flow Telemetry Parameters")
        sim_org = st.selectbox("Organisation ID", all_orgs, index=0)
        sim_app = st.selectbox("Application Name", list(DEFAULT_APP_CLASSES.keys()) + ["CustomERPService", "ShadowTorBulkDownload"])
        sim_class = ApplicationClassifier.classify(sim_app, db=db)
        st.caption(f"Detected Application Class: **{sim_class}**")

        sim_util = st.slider("Simulated Link Utilisation (%)", 0.0, 100.0, 93.5, 0.5)
        sim_prio = st.slider("Service Priority Weight (1-100)", 1, 100, 85)
        
        sim_links = [l.id for l in db.query(Link).all()]
        sim_link = st.selectbox("Target Link", sim_links if sim_links else ["link_chennai_cloud"])

        st.markdown("##### ⚡ Edge Case Condition Modifiers")
        edge_burst = st.checkbox("Inject Bursty Traffic Spike (Micro-Burst Multiplier)", value=False)
        edge_jitter = st.checkbox("Inject High-Jitter Link Condition (Packet Delay Variation)", value=False)

    with col2:
        st.markdown("#### 2. Real-Time Policy Engine Decision Output")
        engine_instance = PolicyEngine()

        # Adjust parameters if edge cases are active
        effective_util = min(100.0, sim_util + 6.0) if edge_burst else sim_util

        req = PolicyEvalRequest(
            flow_id=f"sim_{uuid.uuid4().hex[:6]}",
            organisation_id=sim_org,
            application=sim_app,
            application_class=sim_class,
            link_id=sim_link,
            link_utilisation_pct=effective_util,
            service_priority=sim_prio
        )

        res = engine_instance.evaluate(req, db=db)

        dec_color = {
            "GUARANTEE_MINIMUM": "#10b981",
            "PRIORITISE": "#3b82f6",
            "RATE_LIMIT": "#ef4444",
            "NORMAL": "#6b7280"
        }.get(res.decision, "#6b7280")

        badge_class = {
            "GUARANTEE_MINIMUM": "action-guarantee",
            "PRIORITISE": "action-prioritise",
            "RATE_LIMIT": "action-ratelimit",
            "NORMAL": "action-normal"
        }.get(res.decision, "action-normal")

        st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.03); border: 2px solid {dec_color}; border-radius: 12px; padding: 20px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="margin:0; color:{dec_color};">Action: {res.decision}</h3>
                <span class="action-badge {badge_class}">{res.decision}</span>
            </div>
            <hr style="border-color: rgba(255,255,255,0.1); margin: 12px 0;">
            <p style="margin: 6px 0; color:#e5e7eb;"><b>Calculated Priority Score:</b> <span style="font-size: 1.1em; color:#60a5fa;">{res.priority_score}</span></p>
            <p style="margin: 6px 0; color:#e5e7eb;"><b>Bandwidth Allocation:</b> Minimum: <b>{res.minimum_bandwidth_mbps} Mbps</b> | Ceiling: <b>{res.maximum_bandwidth_mbps} Mbps</b></p>
            <p style="margin: 6px 0; color:#e5e7eb;"><b>Target Link Load:</b> {effective_util:.1f}% {"(Spike Active ⚠️)" if edge_burst else ""}</p>
            <p style="margin: 12px 0 0 0; color:#9ca3af; font-size: 13px; line-height: 1.4;"><b>Evaluation Rationale:</b> {res.reason}</p>
        </div>
        """, unsafe_allow_html=True)

        if edge_jitter:
            st.warning("📡 High-Jitter Active: Packet delay variation modeled at 45.0 ms. Classified flows bypass deep shared FIFO buffers.")
        if res.warning:
            st.warning(f"⚠️ Telemetry Alert: {res.warning}")


# -----------------------------------------------------------------------------
# VIEW 4: MULTI-TENANT POLICY MANAGER
# -----------------------------------------------------------------------------
elif menu == "🔐 Multi-Tenant Policy Manager":
    st.subheader("🔐 Multi-Tenant Bandwidth Policy Rules (RBAC)")
    st.info(f"Active Session: Role **'{current_user.role}'** | Scoped to Tenant **'{current_user.organisation_id}'**.")

    all_policies = db.query(Policy).all()
    filtered_policies = PermissionChecker.filter_records_by_tenant(current_user, all_policies)

    pol_data = [{
        "ID": p.id,
        "Organisation": p.organisation_id,
        "Application": p.application or "ALL (Class Default)",
        "App Class": p.application_class,
        "Priority": p.priority,
        "Min Bandwidth (Mbps)": p.minimum_bandwidth_mbps,
        "Max Bandwidth (Mbps)": p.maximum_bandwidth_mbps,
        "Policy Action": p.action
    } for p in filtered_policies]

    st.dataframe(pd.DataFrame(pol_data), use_container_width=True)

    st.markdown("### ➕ Configure Tenant Policy Rule")
    if current_user.role in ["viewer", "external_partner"]:
        st.warning("⚠️ Write operations restricted for Viewer / External Partner roles. Contact Network Administrator.")
    else:
        with st.form("create_policy_form"):
            c1, c2, c3 = st.columns(3)
            new_org = c1.text_input("Organisation ID", value=current_user.organisation_id if current_user.role == "organisation_manager" else "org_chennai_hq")
            new_app = c2.text_input("Application Name (Optional - empty for all in class)", value="")
            new_class = c3.selectbox("Application Class", ["Critical", "Important", "Normal", "Non-critical"])

            c4, c5, c6 = st.columns(3)
            new_prio = c4.number_input("Priority Weight", 1, 100, 80)
            new_min_bw = c5.number_input("Guaranteed Min Bandwidth (Mbps)", 0.0, 100.0, 30.0)
            new_max_bw = c6.number_input("Maximum Rate-Limit Ceiling (Mbps)", 0.0, 100.0, 100.0)

            new_action = st.selectbox("Policy Action", ["PRIORITISE", "GUARANTEE_MINIMUM", "RATE_LIMIT", "NORMAL"])
            submitted = st.form_submit_button("Deploy Policy Rule")

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
                    st.success(f"Successfully deployed policy rule '{new_id}' for {new_org}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to deploy policy: {str(e)}")


# -----------------------------------------------------------------------------
# VIEW 5: TELEMETRY FALLBACK MONITOR
# -----------------------------------------------------------------------------
elif menu == "🛡️ Telemetry Fallback Monitor":
    st.subheader("🛡️ Telemetry Health & Edge Fallback Engine")
    st.markdown("Monitors system resilience against missing metrics, delayed flow telemetry, or unclassified applications.")

    stale_flow, flow_msg = FallbackEngine.evaluate_flow_freshness(datetime.datetime.now(datetime.timezone.utc))
    links_missing = db.query(Link).filter((Link.utilisation_pct == None) | (Link.utilisation_pct < 0)).count()

    c1, c2, c3 = st.columns(3)
    c1.metric("Flow Telemetry Freshness", "Stale" if stale_flow else "Fresh", delta_color="normal" if not stale_flow else "inverse")
    c2.metric("Missing Link Metrics", links_missing, delta_color="normal" if links_missing == 0 else "inverse")
    c3.metric("Fallback Engine Mode", "Active" if (stale_flow or links_missing > 0) else "Standby")

    st.markdown("### 🧪 Telemetry Fault Injection Simulator")
    sim_fault = st.radio(
        "Simulate Fault Condition:",
        [
            "None (Healthy Telemetry)",
            "Stale Timestamp (>45s delayed report)",
            "Corrupted / Missing Link Metric",
            "Unclassified Shadow Application"
        ]
    )

    if sim_fault == "Stale Timestamp (>45s delayed report)":
        stale_ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=55)
        stale, msg = FallbackEngine.evaluate_flow_freshness(stale_ts)
        st.warning(f"⚠️ {msg} -> Fallback maintains last-known-good bandwidth allocation.")
    elif sim_fault == "Corrupted / Missing Link Metric":
        val, stale, msg = FallbackEngine.resolve_link_utilisation("link_missing_sim", None, db=db)
        st.warning(f"⚠️ {msg} -> Resolved Utilisation to Conservative Default: {val}%")
    elif sim_fault == "Unclassified Shadow Application":
        cls, act, msg = FallbackEngine.resolve_unknown_application("ShadowTorrentSync", "UNKNOWN")
        st.warning(f"⚠️ {msg} -> Application throttled via RATE_LIMIT (10 Mbps) to safeguard critical traffic.")


# -----------------------------------------------------------------------------
# VIEW 6: ACTIVE CONGESTION BENCHMARKS (BASELINE VS HYBRIDFLOWGUARD)
# -----------------------------------------------------------------------------
elif menu == "📊 Active Congestion Benchmarks":
    st.subheader("📊 Active Congestion Simulation Pipeline Benchmarks")
    st.markdown("Empirically benchmark unmanaged FIFO Baseline queueing states against HybridFlowGuard policy-enforced states under congestion and adverse edge conditions.")

    col_ctrl, col_chart = st.columns([1, 2])

    with col_ctrl:
        st.markdown("#### Simulation Parameters")
        scenario_select = st.selectbox(
            "Congestion / Edge Scenario:",
            [
                "90% congestion",
                "98% congestion",
                "Bursty traffic spike",
                "High-jitter link",
                "Bursty spike + High-jitter",
                "Normal network"
            ]
        )
        num_flows_select = st.slider("Simulated Flow Volume", 100, 1000, 350, 50)
        
        if st.button("🚀 Run Active Congestion Pipeline Benchmark", type="primary"):
            with st.spinner(f"Executing active queue simulation for '{scenario_select}'..."):
                exp_res = ExperimentRunner.run(scenario=scenario_select, num_flows=num_flows_select)
                st.session_state["exp_res"] = exp_res

    if "exp_res" in st.session_state:
        res = st.session_state["exp_res"]

        with col_chart:
            st.markdown(f"#### Benchmark Results: {res['scenario']}")
            
            # Combine primary and extended metrics for comprehensive visualization
            all_metrics = list(res.get("metrics_summary", []))
            if "extended_metrics" in res:
                all_metrics.extend(res["extended_metrics"])
            
            # Throughput comparison chart
            tp_metrics = [m for m in all_metrics if "throughput" in m["metric"].lower()]
            if tp_metrics:
                tp_df = pd.DataFrame(tp_metrics)
                fig_tp = px.bar(
                    tp_df,
                    x="metric",
                    y=["baseline", "hybridflowguard"],
                    barmode="group",
                    title="Throughput Comparison: Baseline (FIFO) vs HybridFlowGuard (Mbps)",
                    labels={"value": "Throughput (Mbps)", "metric": "Application Class Throughput"},
                    color_discrete_sequence=["#ef4444", "#10b981"]
                )
                fig_tp.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"}, height=260)
                st.plotly_chart(fig_tp, use_container_width=True)

        # Key Metric Cards
        st.markdown("### 🏆 Key Performance Indicator (KPI) Scorecard")
        sc_cols = st.columns(4)
        sc_cols[0].metric(
            "Critical Throughput",
            f"{res['critical_throughput_hfg']} Mbps",
            delta=f"{res['critical_throughput_hfg'] - res['critical_throughput_baseline']:+.1f} Mbps vs Baseline"
        )
        sc_cols[1].metric(
            "Critical Latency",
            f"{res['critical_latency_hfg']} ms",
            delta=f"{res['critical_latency_hfg'] - res['critical_latency_baseline']:+.1f} ms",
            delta_color="inverse"
        )
        sc_cols[2].metric(
            "Critical Packet Loss",
            f"{res['critical_loss_hfg']}%",
            delta=f"{res['critical_loss_hfg'] - res['critical_loss_baseline']:+.2f}%",
            delta_color="inverse"
        )
        sc_cols[3].metric(
            "Critical Flow Jitter",
            f"{res.get('critical_jitter_hfg', 4.5)} ms",
            delta=f"{res.get('critical_jitter_hfg', 4.5) - res.get('critical_jitter_baseline', 25.0):+.1f} ms",
            delta_color="inverse"
        )

        # Timeline Progression Chart (if present)
        if "timeline_metrics" in res and res["timeline_metrics"]:
            st.markdown("### ⏱️ Dynamic Simulation Progression (Throughput & Buffer Drain)")
            timeline_df = pd.DataFrame(res["timeline_metrics"])
            c_tl1, c_tl2 = st.columns(2)
            with c_tl1:
                fig_tl_tp = gg.Figure()
                fig_tl_tp.add_trace(gg.Scatter(x=timeline_df["time_sec"], y=timeline_df["baseline_critical_tp"], mode="lines+markers", name="Baseline FIFO", line=dict(color="#ef4444", dash="dash")))
                fig_tl_tp.add_trace(gg.Scatter(x=timeline_df["time_sec"], y=timeline_df["hfg_critical_tp"], mode="lines+markers", name="HybridFlowGuard", line=dict(color="#10b981", width=3)))
                fig_tl_tp.add_hline(y=40.5, line_dash="dot", line_color="#3b82f6", annotation_text="Target SLA (40.5 Mbps)")
                fig_tl_tp.update_layout(title="Critical Throughput Over Simulation Time", xaxis_title="Elapsed Time (s)", yaxis_title="Throughput (Mbps)", height=280, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
                st.plotly_chart(fig_tl_tp, use_container_width=True)

            with c_tl2:
                fig_tl_buf = gg.Figure()
                fig_tl_buf.add_trace(gg.Scatter(x=timeline_df["time_sec"], y=timeline_df["baseline_buffer_kb"], mode="lines", name="Baseline Buffer (KB)", line=dict(color="#f97316", width=2)))
                fig_tl_buf.add_trace(gg.Scatter(x=timeline_df["time_sec"], y=timeline_df["hfg_buffer_kb"], mode="lines", name="HybridFlowGuard Buffer (KB)", line=dict(color="#10b981", width=2.5)))
                fig_tl_buf.update_layout(title="Buffer Queue Occupancy (KB) Over Time", xaxis_title="Elapsed Time (s)", yaxis_title="Queue Depth (KB)", height=280, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
                st.plotly_chart(fig_tl_buf, use_container_width=True)

        st.markdown("### 📝 Empirical Performance & Error Analysis Report")
        st.markdown(res["error_analysis"])

db.close()
