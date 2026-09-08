import pytest
import datetime
from app.fallback import FallbackEngine, TELEMETRY_STALE_THRESHOLD_SECONDS
from app.database import SessionLocal, engine, Base
from app.models import Link, Policy

@pytest.fixture(scope="module")
def setup_fallback_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Add a link for DB fallback test
    link = db.query(Link).filter(Link.id == "link_fallback_test").first()
    if not link:
        db.add(Link(
            id="link_fallback_test",
            name="Fallback Test Link",
            source="Site A",
            destination="Site B",
            capacity_mbps=100.0,
            utilisation_pct=82.5,
            status="active"
        ))
    
    # Add tenant policy
    pol = db.query(Policy).filter(Policy.id == "pol_tenant_iso").first()
    if not pol:
        db.add(Policy(
            id="pol_tenant_iso",
            organisation_id="org_iso_tenant_a",
            application="VoIP",
            application_class="Critical",
            priority=100,
            minimum_bandwidth_mbps=40.0,
            maximum_bandwidth_mbps=100.0,
            action="GUARANTEE_MINIMUM"
        ))
    db.commit()
    yield db
    db.close()

def test_evaluate_flow_freshness_fresh():
    now = datetime.datetime.utcnow()
    is_stale, warning = FallbackEngine.evaluate_flow_freshness(now)
    assert not is_stale
    assert warning is None

def test_evaluate_flow_freshness_stale():
    old_ts = datetime.datetime.utcnow() - datetime.timedelta(seconds=45)
    is_stale, warning = FallbackEngine.evaluate_flow_freshness(old_ts)
    assert is_stale
    assert warning is not None
    assert "Stale flow telemetry detected" in warning

def test_evaluate_flow_freshness_missing():
    is_stale, warning = FallbackEngine.evaluate_flow_freshness(None)
    assert is_stale
    assert "timestamp missing" in warning

def test_resolve_link_utilisation_valid():
    util, is_stale, warning = FallbackEngine.resolve_link_utilisation("link_test_valid", 65.0)
    assert util == 65.0
    assert not is_stale
    assert warning is None

def test_resolve_link_utilisation_from_db(setup_fallback_db):
    db = setup_fallback_db
    util, is_stale, warning = FallbackEngine.resolve_link_utilisation("link_fallback_test", None, db=db)
    assert util == 82.5
    assert is_stale
    assert "Using last DB recorded value" in warning

def test_resolve_link_utilisation_from_cache():
    # Pre-populate cache by resolving valid value
    FallbackEngine.resolve_link_utilisation("link_cached_test", 78.0)
    # Now query with None
    util, is_stale, warning = FallbackEngine.resolve_link_utilisation("link_cached_test", None)
    assert util == 78.0
    assert is_stale
    assert "Fallback to last-known-good value" in warning

def test_resolve_link_utilisation_default():
    util, is_stale, warning = FallbackEngine.resolve_link_utilisation("link_non_existent_12345", None)
    assert util == 50.0
    assert is_stale
    assert "Defaulting conservatively" in warning

def test_resolve_unknown_application():
    res_cls, action, warning = FallbackEngine.resolve_unknown_application("MysteryApp", "UNKNOWN")
    assert res_cls == "UNKNOWN"
    assert action == "RATE_LIMIT"
    assert warning is not None
    assert "Unknown application" in warning

def test_get_isolated_org_policy(setup_fallback_db):
    db = setup_fallback_db
    # Matching org and app
    pol = FallbackEngine.get_isolated_org_policy(db, "org_iso_tenant_a", "VoIP", "Critical")
    assert pol is not None
    assert pol.id == "pol_tenant_iso"

    # Non-matching org (tenant isolation check)
    pol_other = FallbackEngine.get_isolated_org_policy(db, "org_iso_tenant_b", "VoIP", "Critical")
    assert pol_other is None
