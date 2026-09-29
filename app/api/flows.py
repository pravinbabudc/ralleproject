"""
Flow Records & Real-Time Policy Evaluation API Endpoints.

Handles flow ingestion, real-time dynamic policy evaluation, tenant filtering,
and synthetic flow telemetry management.
"""

import uuid
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import FlowRecord
from app.schemas import FlowRecordOut, FlowRecordCreate, PolicyEvalRequest, PolicyEvalResult
from app.classifier import ApplicationClassifier
from app.policy_engine import PolicyEngine
from app.permissions import PermissionChecker, UserContext
from app.api.organisations import get_current_user_context

router = APIRouter(tags=["Flow Records & Policy Evaluation"])
engine = PolicyEngine()


@router.get(
    "/flows",
    response_model=List[FlowRecordOut],
    summary="Retrieve tenant-filtered flow records",
    description="Returns recent network flow telemetry records filtered strictly by caller tenant context."
)
def get_flows(
    limit: int = 200,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
) -> List[FlowRecord]:
    """
    Retrieve ingested flow records scoped by tenant isolation.
    
    Parameters:
    - limit: Maximum number of flow records to return (default: 200).
    - user: Authenticated UserContext derived from RBAC headers.
    
    Returns:
    - List[FlowRecord]: Filtered flow records ordered by newest timestamp.
    """
    query = db.query(FlowRecord).order_by(FlowRecord.timestamp.desc())
    all_flows = query.limit(limit).all()
    # Apply tenant data isolation: org managers see strictly their tenant's flows
    return PermissionChecker.filter_records_by_tenant(user, all_flows)


@router.post(
    "/flows",
    response_model=FlowRecordOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest network flow and evaluate bandwidth policy",
    description="Ingests a new flow telemetry record and synchronously evaluates policy action."
)
def create_flow(
    flow_in: FlowRecordCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
) -> FlowRecord:
    """
    Ingest a new flow record and evaluate bandwidth policy on ingestion.
    
    Processing Steps:
    1. Validates caller RBAC write permissions.
    2. Resolves application class if not provided via classifier.
    3. Evaluates real-time policy action (GUARANTEE_MINIMUM, PRIORITISE, RATE_LIMIT, NORMAL).
    4. Persists flow telemetry record with assigned policy action in database.
    """
    PermissionChecker.validate_role_for_write(user)

    flow_id = f"flow_{uuid.uuid4().hex[:10]}"
    app_class = flow_in.application_class or ApplicationClassifier.classify(flow_in.application, db=db)
    link_util = flow_in.link_utilisation_pct if flow_in.link_utilisation_pct is not None else 50.0

    now_utc = flow_in.timestamp or datetime.datetime.now(datetime.timezone.utc)

    # Synchronous real-time policy evaluation
    eval_req = PolicyEvalRequest(
        flow_id=flow_id,
        organisation_id=flow_in.organisation_id,
        application=flow_in.application,
        application_class=app_class,
        link_id=flow_in.link_id,
        link_utilisation_pct=link_util,
        service_priority=flow_in.service_priority,
        timestamp=now_utc
    )

    eval_res = engine.evaluate(eval_req, db=db)

    # Persist flow telemetry with assigned policy decision
    db_flow = FlowRecord(
        id=flow_id,
        timestamp=now_utc,
        organisation_id=flow_in.organisation_id,
        source_location=flow_in.source_location,
        destination=flow_in.destination,
        user_id=flow_in.user_id,
        user_type=flow_in.user_type,
        application=flow_in.application,
        application_class=app_class,
        protocol=flow_in.protocol,
        source_ip=flow_in.source_ip,
        destination_ip=flow_in.destination_ip,
        bytes=flow_in.bytes,
        packets=flow_in.packets,
        latency_ms=flow_in.latency_ms,
        packet_loss_pct=flow_in.packet_loss_pct,
        jitter_ms=getattr(flow_in, "jitter_ms", 1.0) or 1.0,
        burst_factor=getattr(flow_in, "burst_factor", 1.0) or 1.0,
        link_id=flow_in.link_id,
        link_capacity_mbps=flow_in.link_capacity_mbps,
        link_utilisation_pct=link_util,
        service_priority=flow_in.service_priority,
        policy_action=eval_res.decision
    )

    db.add(db_flow)
    db.commit()
    db.refresh(db_flow)

    return db_flow


@router.post(
    "/policy/evaluate",
    response_model=PolicyEvalResult,
    summary="Direct policy engine evaluation endpoint",
    description="Evaluates dynamic bandwidth policy for a flow without persisting the flow record."
)
def evaluate_policy_endpoint(
    req: PolicyEvalRequest,
    db: Session = Depends(get_db)
) -> PolicyEvalResult:
    """
    Directly evaluate dynamic bandwidth policy for a flow context.
    
    Calculates priority score, evaluates link saturation threshold,
    and returns minimum/maximum bandwidth limits with human-readable rationale.
    """
    return engine.evaluate(req, db=db)
