"""
Organisations, Users & Network Infrastructure Topology Endpoints.

Provides administrative visibility into monitored network links, application catalogs,
tenant organizations, and user accounts under Role-Based Access Control (RBAC).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Organisation, Link, Application, User
from app.schemas import OrganisationOut, LinkOut, ApplicationOut, UserOut
from app.permissions import PermissionChecker, UserContext

router = APIRouter(tags=["Organisations & Infrastructure"])


def get_current_user_context(
    x_user_role: Optional[str] = Header("admin", description="Simulated RBAC role header: admin, network_manager, organisation_manager, external_partner, viewer"),
    x_organisation_id: Optional[str] = Header("org_chennai_hq", description="Tenant organization scope identifier"),
    x_username: Optional[str] = Header("admin_user", description="Caller username for audit tracking")
) -> UserContext:
    """
    Dependency helper extracting caller context from HTTP headers.
    
    Provides lightweight authentication simulation for multi-tenant isolation
    and RBAC permission enforcement.
    """
    return UserContext(
        user_id="usr_current",
        username=x_username or "admin_user",
        organisation_id=x_organisation_id or "org_chennai_hq",
        role=x_user_role or "admin"
    )


@router.get(
    "/organisations",
    response_model=List[OrganisationOut],
    summary="List tenant organisations",
    description="Returns organizations filtered by caller role (Admins see all; Org Managers see own org)."
)
def get_organisations(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
) -> List[Organisation]:
    """List organisations with tenant isolation applied based on user role."""
    all_orgs = db.query(Organisation).all()
    return PermissionChecker.filter_records_by_tenant(user, all_orgs, org_id_attr="id")


@router.get(
    "/links",
    response_model=List[LinkOut],
    summary="List monitored network links",
    description="Retrieves physical and virtual link topologies, rated capacities (Mbps), and current utilisation."
)
def get_links(db: Session = Depends(get_db)) -> List[Link]:
    """List network links, endpoints, capacities, and instantaneous utilisation."""
    return db.query(Link).all()


@router.get(
    "/applications",
    response_model=List[ApplicationOut],
    summary="List registered applications catalog",
    description="Returns pre-classified application registry with default QoS priority weights."
)
def get_applications(db: Session = Depends(get_db)) -> List[Application]:
    """List registered applications, default classifications, and baseline priority weights."""
    return db.query(Application).all()


@router.get(
    "/users",
    response_model=List[UserOut],
    summary="List system users",
    description="Lists system user identities scoped to tenant or globally for platform admins."
)
def get_users(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
) -> List[User]:
    """
    List system users.
    
    - Admin / Network Manager: Receives all system users across all organisations.
    - Organisation Manager: Receives strictly users belonging to their assigned organisation.
    """
    if user.role not in ["admin", "network_manager"]:
        return db.query(User).filter(User.organisation_id == user.organisation_id).all()
    return db.query(User).all()
