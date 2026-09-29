"""
System Health & Telemetry Status API Endpoints.

Provides readiness checks, operational uptime status, and deep telemetry anomaly
monitoring (stale flow detection, missing link sensors, unclassified application tracking).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FlowRecord, Link, Application
from app.schemas import TelemetryStatus
import datetime

router = APIRouter(tags=["Health & Status"])


@router.get(
    "/health",
    summary="System health & readiness check",
    description="Returns service uptime status, version metadata, and current server UTC timestamp."
)
def get_health():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "HybridFlowGuard Policy Engine",
        "version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


@router.get(
    "/failures/status",
    response_model=TelemetryStatus,
    summary="Telemetry health & fallback status monitor",
    description="Monitors telemetry stream freshness, missing link metrics, and active fallback safeguards."
)
def get_failure_status(db: Session = Depends(get_db)) -> TelemetryStatus:
    """
    Monitor system telemetry health, stale data, and fallback activity.
    
    Evaluates:
    - Flow telemetry freshness: Flags stale telemetry if newest flow is older than 30 seconds.
    - Missing link utilisation: Detects links where utilisation sensor is None or corrupted (< 0).
    - Unclassified application count: Identifies presence of UNKNOWN shadow traffic.
    - Fallback engine state: Operational (all healthy) vs Degraded (active fallback engaged).
    """
    latest_flow = db.query(FlowRecord).order_by(FlowRecord.timestamp.desc()).first()

    last_flow_ts_str = latest_flow.timestamp.isoformat() if latest_flow and latest_flow.timestamp else None
    
    # 1. Evaluate flow telemetry freshness boundary (threshold: 30 seconds)
    stale_flow_detected = False
    if latest_flow and latest_flow.timestamp:
        # Normalize naive timestamp to UTC if needed
        flow_ts = latest_flow.timestamp
        if flow_ts.tzinfo is None:
            now = datetime.datetime.utcnow()
        else:
            now = datetime.datetime.now(datetime.timezone.utc)
        age_sec = (now - flow_ts).total_seconds()
        if age_sec > 30:
            stale_flow_detected = True

    # 2. Check for missing or corrupted link utilisation sensors
    links_with_missing_util = db.query(Link).filter((Link.utilisation_pct == None) | (Link.utilisation_pct < 0)).count()
    missing_util_detected = links_with_missing_util > 0

    # 3. Track unclassified application flows (Shadow IT risk)
    unknown_apps_count = db.query(FlowRecord).filter(FlowRecord.application_class == "UNKNOWN").count()

    fallback_active = stale_flow_detected or missing_util_detected or (unknown_apps_count > 0)

    message = "All telemetry data sources online and healthy."
    if fallback_active:
        message = "Telemetry anomalies detected. Telemetry fallback active to protect critical applications."

    return TelemetryStatus(
        status="degraded" if fallback_active else "operational",
        last_flow_timestamp=last_flow_ts_str,
        last_utilisation_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        stale_flow_detected=stale_flow_detected,
        missing_link_utilisation_detected=missing_util_detected,
        unknown_applications_count=unknown_apps_count,
        fallback_active=fallback_active,
        message=message
    )
