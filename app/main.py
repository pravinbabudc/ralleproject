import os
import uuid
import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.models import Organisation, User, Link, Application, Policy, FlowRecord, AuditLog
from app.classifier import DEFAULT_APP_CLASSES, DEFAULT_APP_PRIORITIES
from app.simulator import CongestionSimulator
from app.api import health, organisations, policies, flows, experiments

app = FastAPI(
    title="HybridFlowGuard – Application-Aware Bandwidth Policy Engine API",
    description="Backend REST API for dynamic bandwidth policy evaluation, link monitoring, multi-tenant isolation, and telemetry fallback.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(health.router)
app.include_router(organisations.router)
app.include_router(policies.router)
app.include_router(flows.router)
app.include_router(experiments.router)

def seed_database():
    """Populate database with initial organisations, users, links, apps, and sample flow records."""
    db = SessionLocal()
    try:
        # 1. Seed Organisations
        if db.query(Organisation).count() == 0:
            orgs = [
                Organisation(id="org_chennai_hq", name="Chennai HQ Office", status="active"),
                Organisation(id="org_bangalore_hub", name="Bangalore R&D Hub", status="active"),
                Organisation(id="org_mumbai_hub", name="Mumbai Regional Office", status="active"),
                Organisation(id="org_aws_cloud", name="AWS Cloud Network", status="active"),
                Organisation(id="org_azure_cloud", name="Azure Cloud Network", status="active"),
                Organisation(id="org_remote_work", name="Remote Employees", status="active"),
                Organisation(id="org_external_partner", name="External Partner Network", status="active")
            ]
            db.add_all(orgs)

        # 2. Seed Users
        if db.query(User).count() == 0:
            users = [
                User(id="usr_admin", username="admin_user", organisation_id="org_chennai_hq", role="admin"),
                User(id="usr_netmgr", username="net_mgr", organisation_id="org_chennai_hq", role="network_manager"),
                User(id="usr_chennai", username="chennai_mgr", organisation_id="org_chennai_hq", role="organisation_manager"),
                User(id="usr_bangalore", username="bangalore_mgr", organisation_id="org_bangalore_hub", role="organisation_manager"),
                User(id="usr_partner", username="ext_partner", organisation_id="org_external_partner", role="external_partner"),
                User(id="usr_viewer", username="guest_viewer", organisation_id="org_chennai_hq", role="viewer")
            ]
            db.add_all(users)

        # 3. Seed Links
        if db.query(Link).count() == 0:
            links = [
                Link(id="link_chennai_cloud", name="Chennai HQ to Cloud DirectConnect", source="Chennai Office", destination="AWS Cloud", capacity_mbps=100.0, utilisation_pct=55.0, status="active"),
                Link(id="link_bangalore_cloud", name="Bangalore R&D ExpressRoute", source="Bangalore Office", destination="Azure Cloud", capacity_mbps=100.0, utilisation_pct=60.0, status="active"),
                Link(id="link_mumbai_cloud", name="Mumbai Branch MPLS", source="Mumbai Office", destination="AWS Cloud", capacity_mbps=100.0, utilisation_pct=45.0, status="active"),
                Link(id="link_aws_backbone", name="AWS Core Transit Gateway", source="AWS Cloud", destination="Core Datacenter", capacity_mbps=1000.0, utilisation_pct=72.0, status="active"),
                Link(id="link_azure_backbone", name="Azure Core Peering", source="Azure Cloud", destination="Core Datacenter", capacity_mbps=1000.0, utilisation_pct=68.0, status="active"),
                Link(id="link_vpn_gateway", name="Remote VPN Concentrator", source="Remote Employees", destination="Chennai Office", capacity_mbps=100.0, utilisation_pct=88.0, status="active"),
                Link(id="link_partner_extranet", name="External Partner Extranet Link", source="External Partners", destination="DMZ Gateway", capacity_mbps=50.0, utilisation_pct=40.0, status="active")
            ]
            db.add_all(links)

        # 4. Seed Applications
        if db.query(Application).count() == 0:
            apps = []
            for app_name, app_cls in DEFAULT_APP_CLASSES.items():
                priority = DEFAULT_APP_PRIORITIES.get(app_cls, 50)
                apps.append(Application(
                    id=f"app_{app_name.lower().replace(' ', '_')}",
                    name=app_name,
                    application_class=app_cls,
                    default_priority=priority
                ))
            db.add_all(apps)

        # 5. Seed Initial Policies
        if db.query(Policy).count() == 0:
            policies = [
                Policy(id="pol_def_critical", organisation_id="org_chennai_hq", application=None, application_class="Critical", priority=100, minimum_bandwidth_mbps=40.0, maximum_bandwidth_mbps=100.0, action="PRIORITISE"),
                Policy(id="pol_def_noncritical", organisation_id="org_chennai_hq", application=None, application_class="Non-critical", priority=10, minimum_bandwidth_mbps=0.0, maximum_bandwidth_mbps=15.0, action="RATE_LIMIT"),
                Policy(id="pol_partner_default", organisation_id="org_external_partner", application=None, application_class="Normal", priority=30, minimum_bandwidth_mbps=0.0, maximum_bandwidth_mbps=25.0, action="NORMAL")
            ]
            db.add_all(policies)

        # 6. Seed Sample Flow Records
        if db.query(FlowRecord).count() == 0:
            sample_flows = CongestionSimulator.generate_dataset(count=300, scenario="Normal network")
            for _, row in sample_flows.iterrows():
                fr = FlowRecord(
                    id=row["id"],
                    timestamp=datetime.datetime.fromisoformat(row["timestamp"]),
                    organisation_id=row["organisation_id"],
                    source_location=row["source_location"],
                    destination=row["destination"],
                    user_id=row["user_id"],
                    user_type=row["user_type"],
                    application=row["application"],
                    application_class=row["application_class"],
                    protocol=row["protocol"],
                    source_ip=row["source_ip"],
                    destination_ip=row["destination_ip"],
                    bytes=row["bytes"],
                    packets=row["packets"],
                    latency_ms=row["latency_ms"],
                    packet_loss_pct=row["packet_loss_pct"],
                    link_id=row["link_id"],
                    link_capacity_mbps=row["link_capacity_mbps"],
                    link_utilisation_pct=row["link_utilisation_pct"],
                    service_priority=row["service_priority"],
                    policy_action=row["policy_action"]
                )
                db.add(fr)

        # 7. Audit log seed
        if db.query(AuditLog).count() == 0:
            db.add(AuditLog(
                id=f"audit_init",
                timestamp=datetime.datetime.utcnow(),
                user_id="system",
                action="INITIALIZE_SYSTEM",
                details="HybridFlowGuard database initialized with default tenant policies and infrastructure metadata."
            ))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Database seeding warning: {str(e)}")
    finally:
        db.close()

def run_migrations():
    """Ensure newly introduced columns exist in SQLite database without requiring external tools."""
    from sqlalchemy import inspect, text
    with engine.connect() as conn:
        insp = inspect(conn)
        existing_tables = insp.get_table_names()
        if "flow_records" in existing_tables:
            cols = [c["name"] for c in insp.get_columns("flow_records")]
            if "jitter_ms" not in cols:
                conn.execute(text("ALTER TABLE flow_records ADD COLUMN jitter_ms FLOAT DEFAULT 1.0"))
            if "burst_factor" not in cols:
                conn.execute(text("ALTER TABLE flow_records ADD COLUMN burst_factor FLOAT DEFAULT 1.0"))
            conn.commit()

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(bind=engine)
    run_migrations()
    seed_database()
