import pytest
from fastapi import HTTPException
from app.permissions import PermissionChecker, UserContext

def test_validate_role_for_write_permitted_roles():
    admin = UserContext(user_id="u1", username="admin", organisation_id="org_chennai_hq", role="admin")
    netmgr = UserContext(user_id="u2", username="netmgr", organisation_id="org_chennai_hq", role="network_manager")
    orgmgr = UserContext(user_id="u3", username="orgmgr", organisation_id="org_bangalore_hub", role="organisation_manager")

    PermissionChecker.validate_role_for_write(admin)
    PermissionChecker.validate_role_for_write(netmgr)
    PermissionChecker.validate_role_for_write(orgmgr)

def test_validate_role_for_write_restricted_roles():
    viewer = UserContext(user_id="u4", username="viewer", organisation_id="org_chennai_hq", role="viewer")
    partner = UserContext(user_id="u5", username="partner", organisation_id="org_external_partner", role="external_partner")

    with pytest.raises(HTTPException) as exc_info:
        PermissionChecker.validate_role_for_write(viewer)
    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info_p:
        PermissionChecker.validate_role_for_write(partner)
    assert exc_info_p.value.status_code == 403

def test_enforce_tenant_isolation_admin():
    admin = UserContext(user_id="u1", username="admin", organisation_id="org_chennai_hq", role="admin")
    # Admin can access any tenant
    PermissionChecker.enforce_tenant_isolation(admin, "org_mumbai_hub")
    PermissionChecker.enforce_tenant_isolation(admin, "org_external_partner")

def test_enforce_tenant_isolation_org_manager():
    orgmgr = UserContext(user_id="u3", username="orgmgr", organisation_id="org_bangalore_hub", role="organisation_manager")
    # Same tenant permitted
    PermissionChecker.enforce_tenant_isolation(orgmgr, "org_bangalore_hub")
    
    # Different tenant denied
    with pytest.raises(HTTPException) as exc:
        PermissionChecker.enforce_tenant_isolation(orgmgr, "org_chennai_hq")
    assert exc.value.status_code == 403

def test_enforce_tenant_isolation_external_partner():
    partner = UserContext(user_id="u5", username="partner", organisation_id="org_external_partner", role="external_partner")
    # Access to partner org permitted
    PermissionChecker.enforce_tenant_isolation(partner, "org_external_partner")

    # Access to non-partner org denied
    with pytest.raises(HTTPException) as exc:
        PermissionChecker.enforce_tenant_isolation(partner, "org_chennai_hq")
    assert exc.value.status_code == 403

class DummyRecord:
    def __init__(self, organisation_id: str):
        self.organisation_id = organisation_id

def test_filter_records_by_tenant():
    records = [
        DummyRecord("org_chennai_hq"),
        DummyRecord("org_bangalore_hub"),
        DummyRecord("org_external_partner")
    ]

    admin = UserContext(user_id="u1", username="admin", organisation_id="org_chennai_hq", role="admin")
    orgmgr = UserContext(user_id="u3", username="orgmgr", organisation_id="org_bangalore_hub", role="organisation_manager")
    partner = UserContext(user_id="u5", username="partner", organisation_id="org_external_partner", role="external_partner")

    assert len(PermissionChecker.filter_records_by_tenant(admin, records)) == 3
    
    filtered_orgmgr = PermissionChecker.filter_records_by_tenant(orgmgr, records)
    assert len(filtered_orgmgr) == 1
    assert filtered_orgmgr[0].organisation_id == "org_bangalore_hub"

    filtered_partner = PermissionChecker.filter_records_by_tenant(partner, records)
    assert len(filtered_partner) == 1
    assert filtered_partner[0].organisation_id == "org_external_partner"
