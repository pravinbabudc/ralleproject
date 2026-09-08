import uuid
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Policy, PolicyDecision, AuditLog
from app.schemas import (
    PolicyOut, PolicyCreate, PolicyUpdate,
    PolicyDecisionOut, AuditLogOut
)
from app.permissions import PermissionChecker, UserContext
from app.api.organisations import get_current_user_context

router = APIRouter(tags=["Bandwidth Policies & Audits"])

@router.get("/policies", response_model=List[PolicyOut])
def get_policies(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """Retrieve bandwidth policies filtered by tenant permissions."""
    all_policies = db.query(Policy).all()
    return PermissionChecker.filter_records_by_tenant(user, all_policies)

@router.post("/policies", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
def create_policy(
    policy_in: PolicyCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """Create a new bandwidth policy with RBAC and tenant validation."""
    PermissionChecker.validate_role_for_write(user)
    PermissionChecker.enforce_tenant_isolation(user, policy_in.organisation_id)

    policy_id = f"pol_{uuid.uuid4().hex[:8]}"
    db_policy = Policy(
        id=policy_id,
        organisation_id=policy_in.organisation_id,
        application=policy_in.application,
        application_class=policy_in.application_class,
        priority=policy_in.priority,
        minimum_bandwidth_mbps=policy_in.minimum_bandwidth_mbps,
        maximum_bandwidth_mbps=policy_in.maximum_bandwidth_mbps,
        action=policy_in.action
    )
    db.add(db_policy)

    # Log audit entry
    audit = AuditLog(
        id=f"audit_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.datetime.utcnow(),
        user_id=user.username,
        action="CREATE_POLICY",
        details=f"Created policy '{policy_id}' for Org '{policy_in.organisation_id}': Class={policy_in.application_class}, Action={policy_in.action}"
    )
    db.add(audit)
    db.commit()
    db.refresh(db_policy)

    return db_policy

@router.put("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(
    policy_id: str,
    policy_in: PolicyUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """Update an existing bandwidth policy."""
    PermissionChecker.validate_role_for_write(user)

    db_policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found.")

    PermissionChecker.enforce_tenant_isolation(user, db_policy.organisation_id)

    update_data = policy_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(db_policy, field, val)

    # Audit log
    audit = AuditLog(
        id=f"audit_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.datetime.utcnow(),
        user_id=user.username,
        action="UPDATE_POLICY",
        details=f"Updated policy '{policy_id}' with fields: {list(update_data.keys())}"
    )
    db.add(audit)
    db.commit()
    db.refresh(db_policy)

    return db_policy

@router.get("/policy/decisions", response_model=List[PolicyDecisionOut])
def get_policy_decisions(
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get recorded policy engine decisions."""
    return db.query(PolicyDecision).order_by(PolicyDecision.timestamp.desc()).limit(limit).all()

@router.get("/audit-logs", response_model=List[AuditLogOut])
def get_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """Get administrative audit logs."""
    if user.role in ["viewer", "external_partner"]:
        raise HTTPException(status_code=403, detail="Audit logs are accessible to managers and admins only.")
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
