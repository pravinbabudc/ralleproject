from typing import Optional, List, Any
from fastapi import HTTPException, status
from pydantic import BaseModel

class UserContext(BaseModel):
    user_id: str
    username: str
    organisation_id: str
    role: str  # admin, network_manager, organisation_manager, external_partner, viewer

class PermissionChecker:
    """Multi-tenant security and RBAC validator."""

    @staticmethod
    def validate_role_for_write(user: UserContext) -> None:
        """
        Verify if user has permission to perform write operations (Create, Update, Delete).
        Viewers and External Partners are restricted to read-only access.
        """
        if user.role in ["viewer", "external_partner"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is restricted to read-only operations. Permission denied."
            )

    @staticmethod
    def enforce_tenant_isolation(user: UserContext, target_org_id: str) -> None:
        """
        Ensure non-admin users cannot access or modify data belonging to other tenants.
        """
        if user.role in ["admin", "network_manager"]:
            return  # Cross-tenant access permitted for global admins/network managers

        if user.role == "external_partner":
            if target_org_id != "org_external_partner":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="External partner users are strictly restricted to partner-scoped data."
                )

        if user.role == "organisation_manager":
            if user.organisation_id != target_org_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. User belongs to '{user.organisation_id}' and cannot access data for '{target_org_id}'."
                )

    @staticmethod
    def filter_records_by_tenant(user: UserContext, records: List[Any], org_id_attr: str = "organisation_id") -> List[Any]:
        """
        Filter a list of objects based on tenant isolation rules.
        """
        if user.role in ["admin", "network_manager"]:
            return records

        if user.role == "external_partner":
            return [r for r in records if getattr(r, org_id_attr, None) == "org_external_partner"]

        return [r for r in records if getattr(r, org_id_attr, None) == user.organisation_id]
