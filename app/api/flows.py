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

@router.get("/flows", response_model=List[FlowRecordOut])
def get_flows(
    limit: int = 200,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """Retrieve ingested flow records scoped by tenant isolation."""
    query = db.query(FlowRecord).order_by(FlowRecord.timestamp.desc())
    all_flows = query.limit(limit).all()
    return PermissionChecker.filter_records_by_tenant(user, all_flows)

@router.post("/flows", response_model=FlowRecordOut, status_code=status.HTTP_201_CREATED)
def create_flow(
    flow_in: FlowRecordCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """Ingest a new flow record and evaluate bandwidth policy on ingestion."""
    PermissionChecker.validate_role_for_write(user)

    flow_id = f"flow_{uuid.uuid4().hex[:10]}"
    app_class = flow_in.application_class or ApplicationClassifier.classify(flow_in.application, db=db)
    link_util = flow_in.link_utilisation_pct if flow_in.link_utilisation_pct is not None else 50.0

    eval_req = PolicyEvalRequest(
        flow_id=flow_id,
        organisation_id=flow_in.organisation_id,
        application=flow_in.application,
        application_class=app_class,
        link_id=flow_in.link_id,
        link_utilisation_pct=link_util,
        service_priority=flow_in.service_priority,
        timestamp=flow_in.timestamp or datetime.datetime.utcnow()
    )

    eval_res = engine.evaluate(eval_req, db=db)

    db_flow = FlowRecord(
        id=flow_id,
        timestamp=flow_in.timestamp or datetime.datetime.utcnow(),
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

@router.post("/policy/evaluate", response_model=PolicyEvalResult)
def evaluate_policy_endpoint(
    req: PolicyEvalRequest,
    db: Session = Depends(get_db)
):
    """Directly evaluate dynamic bandwidth policy for a flow context."""
    return engine.evaluate(req, db=db)
