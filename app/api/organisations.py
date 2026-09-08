from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Organisation, Link, Application, User
from app.schemas import OrganisationOut, LinkOut, ApplicationOut, UserOut
from app.permissions import PermissionChecker, UserContext

router = APIRouter(tags=["Organisations & Infrastructure"])

def get_current_user_context(
    x_user_role: Optional[str] = Header("admin"),
    x_organisation_id: Optional[str] = Header("org_chennai_hq"),
    x_username: Optional[str] = Header("admin_user")
) -> UserContext:
    """Dependency helper to extract user context from headers (simulating RBAC auth)."""
    return UserContext(
        user_id="usr_current",
        username=x_username or "admin_user",
        organisation_id=x_organisation_id or "org_chennai_hq",
        role=x_user_role or "admin"
    )

@router.get("/organisations", response_model=List[OrganisationOut])
def get_organisations(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """List organisations with tenant isolation applied based on role."""
    all_orgs = db.query(Organisation).all()
    filtered_orgs = PermissionChecker.filter_records_by_tenant(user, all_orgs, org_id_attr="id")
    return filtered_orgs

@router.get("/links", response_model=List[LinkOut])
def get_links(db: Session = Depends(get_db)):
    """List network links and capacities."""
    return db.query(Link).all()

@router.get("/applications", response_model=List[ApplicationOut])
def get_applications(db: Session = Depends(get_db)):
    """List registered applications and classifications."""
    return db.query(Application).all()

@router.get("/users", response_model=List[UserOut])
def get_users(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user_context)
):
    """List system users."""
    if user.role not in ["admin", "network_manager"]:
        return db.query(User).filter(User.organisation_id == user.organisation_id).all()
    return db.query(User).all()
