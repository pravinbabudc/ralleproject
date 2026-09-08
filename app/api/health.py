from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FlowRecord, Link, Application
from app.schemas import TelemetryStatus
import datetime

router = APIRouter(tags=["Health & Status"])

@router.get("/health")
def get_health():
    """System health endpoint."""
    return {
        "status": "healthy",
        "service": "HybridFlowGuard Policy Engine",
        "version": "1.0.0",
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

@router.get("/failures/status", response_model=TelemetryStatus)
def get_failure_status(db: Session = Depends(get_db)):
    """Monitor system telemetry health, stale data, and fallback activity."""
    latest_flow = db.query(FlowRecord).order_by(FlowRecord.timestamp.desc()).first()

    last_flow_ts_str = latest_flow.timestamp.isoformat() if latest_flow and latest_flow.timestamp else None
    
    stale_flow_detected = False
    if latest_flow and latest_flow.timestamp:
        age_sec = (datetime.datetime.utcnow() - latest_flow.timestamp).total_seconds()
        if age_sec > 30:
            stale_flow_detected = True

    # Check missing link utilisation
    links_with_missing_util = db.query(Link).filter((Link.utilisation_pct == None) | (Link.utilisation_pct < 0)).count()
    missing_util_detected = links_with_missing_util > 0

    # Count unknown applications
    unknown_apps_count = db.query(FlowRecord).filter(FlowRecord.application_class == "UNKNOWN").count()

    fallback_active = stale_flow_detected or missing_util_detected or (unknown_apps_count > 0)

    message = "All telemetry data sources online and healthy."
    if fallback_active:
        message = "Telemetry anomalies detected. Telemetry fallback active to protect critical applications."

    return TelemetryStatus(
        status="degraded" if fallback_active else "operational",
        last_flow_timestamp=last_flow_ts_str,
        last_utilisation_timestamp=datetime.datetime.utcnow().isoformat(),
        stale_flow_detected=stale_flow_detected,
        missing_link_utilisation_detected=missing_util_detected,
        unknown_applications_count=unknown_apps_count,
        fallback_active=fallback_active,
        message=message
    )
