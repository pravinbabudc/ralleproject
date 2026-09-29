"""
Bandwidth Policies & Administrative Audit Log API Endpoints.

Handles CRUD operations for multi-tenant bandwidth policies, policy evaluation
lookups, and security audit log retrieval with Role-Based Access Control (RBAC).
"""

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


@router.get(
    "/policies",
    response_model=List[PolicyOut],
    summary="Retrieve tenant-filtered bandwidth policies",
    description="Returns list of bandwidth policies filtered according to the caller's RBAC role and assigned tenant organisation."
)
def get_policies(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
) -> List[Policy]:
    """
    Retrieve bandwidth policies filtered by tenant permissions.
    
    - Admin / Network Manager: Receives all policies across all organisations.
    - Organisation Manager: Receives strictly policies assigned to their organisation_id.
    - External Partner / Viewer: Receives scoped read-only policies.
    """
    all_policies = db.query(Policy).all()
    return PermissionChecker.filter_records_by_tenant(user, all_policies)


@router.post(
    "/policies",
    response_model=PolicyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bandwidth policy rule",
    description="Deploy a dynamic bandwidth policy. Validates user write permissions and verifies tenant isolation."
)
def create_policy(
    policy_in: PolicyCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
) -> Policy:
    """
    Create a new bandwidth policy with RBAC and tenant validation.
    
    Parameters:
    - policy_in: Schema containing organisation_id, application, application_class,
                 priority weight, minimum/maximum bandwidth (Mbps), and policy action.
                 
    Raises:
    - HTTPException(403): If caller lacks write role or attempts cross-tenant creation.
    """
    # 1. Enforce RBAC write permissions (viewer/external_partner are rejected)
    PermissionChecker.validate_role_for_write(user)

    # 2. Enforce Tenant Isolation (organisation_manager cannot create policy for another org)
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

    # 3. Write immutable audit log entry
    audit = AuditLog(
        id=f"audit_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        user_id=user.username,
        action="CREATE_POLICY",
        details=f"Created policy '{policy_id}' for Org '{policy_in.organisation_id}': Class={policy_in.application_class}, Action={policy_in.action}, MinBW={policy_in.minimum_bandwidth_mbps}Mbps, MaxBW={policy_in.maximum_bandwidth_mbps}Mbps"
    )
    db.add(audit)
    db.commit()
    db.refresh(db_policy)

    return db_policy


@router.put(
    "/policies/{policy_id}",
    response_model=PolicyOut,
    summary="Update an existing bandwidth policy",
    description="Modifies bandwidth allocation thresholds or policy action on an existing rule."
)
def update_policy(
    policy_id: str,
    policy_in: PolicyUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
) -> Policy:
    """
    Update an existing bandwidth policy.
    
    Parameters:
    - policy_id: Unique identifier of policy to modify.
    - policy_in: Optional update fields (priority, min/max bandwidth, action).
    
    Raises:
    - HTTPException(403): If role lacks write permissions or cross-tenant modification attempted.
    - HTTPException(404): If policy_id does not exist in database.
    """
    PermissionChecker.validate_role_for_write(user)

    db_policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found.")

    PermissionChecker.enforce_tenant_isolation(user, db_policy.organisation_id)

    update_data = policy_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(db_policy, field, val)

    # Audit log update action
    audit = AuditLog(
        id=f"audit_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        user_id=user.username,
        action="UPDATE_POLICY",
        details=f"Updated policy '{policy_id}' with modified attributes: {list(update_data.keys())}"
    )
    db.add(audit)
    db.commit()
    db.refresh(db_policy)

    return db_policy


@router.delete(
    "/policies/{policy_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a bandwidth policy rule",
    description="Removes a policy rule from the database and creates an audit trail entry."
)
def delete_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """
    Delete a bandwidth policy rule.
    
    Parameters:
    - policy_id: Unique identifier of policy to remove.
    """
    PermissionChecker.validate_role_for_write(user)

    db_policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found.")

    PermissionChecker.enforce_tenant_isolation(user, db_policy.organisation_id)

    db.delete(db_policy)

    # Log deletion in audit trail
    audit = AuditLog(
        id=f"audit_{uuid.uuid4().hex[:8]}",
        timestamp=datetime.datetime.now(datetime.timezone.utc),
        user_id=user.username,
        action="DELETE_POLICY",
        details=f"Deleted policy '{policy_id}' previously assigned to Org '{db_policy.organisation_id}'"
    )
    db.add(audit)
    db.commit()

    return {"status": "success", "message": f"Policy '{policy_id}' successfully removed."}


@router.get(
    "/policy/decisions",
    response_model=List[PolicyDecisionOut],
    summary="Retrieve recorded policy engine decisions",
    description="Returns real-time decision logs including priority scores and evaluation reasons."
)
def get_policy_decisions(
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[PolicyDecision]:
    """Get recorded policy engine decisions for audit inspection."""
    return db.query(PolicyDecision).order_by(PolicyDecision.timestamp.desc()).limit(limit).all()


@router.get(
    "/audit-logs",
    response_model=List[AuditLogOut],
    summary="Retrieve administrative audit logs",
    description="Provides security audit trail of configuration changes and policy deployments."
)
def get_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
) -> List[AuditLog]:
    """Get administrative audit logs (Restricted to Managers and Admins)."""
    if user.role in ["viewer", "external_partner"]:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Audit logs are reserved for Network Managers and Administrators."
        )
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
