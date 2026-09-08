import pytest
import datetime
from app.policy_engine import PolicyEngine, PolicyEngineConfig
from app.schemas import PolicyEvalRequest
from app.database import SessionLocal, engine, Base
from app.models import Policy, Organisation

@pytest.fixture(scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Ensure test org and policy exist
    org = db.query(Organisation).filter(Organisation.id == "org_test_hq").first()
    if not org:
        db.add(Organisation(id="org_test_hq", name="Test HQ", status="active"))
    
    # Custom policy override for test app
    pol = db.query(Policy).filter(Policy.id == "pol_custom_test").first()
    if not pol:
        db.add(Policy(
            id="pol_custom_test",
            organisation_id="org_test_hq",
            application="CustomApp",
            application_class="Critical",
            priority=95,
            minimum_bandwidth_mbps=60.0,
            maximum_bandwidth_mbps=100.0,
            action="GUARANTEE_MINIMUM"
        ))
    db.commit()
    yield db
    db.close()

def test_priority_score_calculation():
    engine = PolicyEngine()
    # Critical (4.0) * org_chennai_hq (1.2) * priority (100) = 480.0
    score = engine.calculate_priority_score(service_priority=100, app_class="Critical", organisation_id="org_chennai_hq")
    assert score == 480.0

    # Non-critical (1.0) * org_external_partner (0.8) * priority (20) = 16.0
    score_non_crit = engine.calculate_priority_score(service_priority=20, app_class="Non-critical", organisation_id="org_external_partner")
    assert score_non_crit == 16.0

def test_evaluate_severe_congestion_critical_app():
    engine = PolicyEngine()
    req = PolicyEvalRequest(
        flow_id="flow_test_1",
        organisation_id="org_chennai_hq",
        application="ERP",
        application_class="Critical",
        link_id="link_chennai_cloud",
        link_utilisation_pct=96.5,
        service_priority=100
    )
    res = engine.evaluate(req)
    assert res.decision == "GUARANTEE_MINIMUM"
    assert res.minimum_bandwidth_mbps == 50.0
    assert "CRITICAL SEVERE CONGESTION" in res.reason

def test_evaluate_high_congestion_non_critical_app():
    engine = PolicyEngine()
    req = PolicyEvalRequest(
        flow_id="flow_test_2",
        organisation_id="org_mumbai_hub",
        application="Video streaming",
        application_class="Non-critical",
        link_id="link_mumbai_cloud",
        link_utilisation_pct=88.0,
        service_priority=10
    )
    res = engine.evaluate(req)
    assert res.decision == "RATE_LIMIT"
    assert res.maximum_bandwidth_mbps == 15.0
    assert "HIGH CONGESTION DETECTED" in res.reason

def test_evaluate_moderate_congestion_important_app():
    engine = PolicyEngine()
    req = PolicyEvalRequest(
        flow_id="flow_test_3",
        organisation_id="org_bangalore_hub",
        application="Microsoft Teams",
        application_class="Important",
        link_id="link_bangalore_cloud",
        link_utilisation_pct=75.0,
        service_priority=70
    )
    res = engine.evaluate(req)
    assert res.decision == "PRIORITISE"
    assert res.minimum_bandwidth_mbps == 25.0
    assert "MODERATE CONGESTION" in res.reason

def test_evaluate_normal_congestion():
    engine = PolicyEngine()
    req = PolicyEvalRequest(
        flow_id="flow_test_4",
        organisation_id="org_chennai_hq",
        application="General web browsing",
        application_class="Normal",
        link_id="link_chennai_cloud",
        link_utilisation_pct=45.0,
        service_priority=40
    )
    res = engine.evaluate(req)
    assert res.decision == "NORMAL"
    assert "Link utilisation normal" in res.reason

def test_evaluate_unknown_application():
    engine = PolicyEngine()
    req = PolicyEvalRequest(
        flow_id="flow_test_5",
        organisation_id="org_chennai_hq",
        application="UnregisteredAppXYZ",
        application_class=None,
        link_id="link_chennai_cloud",
        link_utilisation_pct=50.0,
        service_priority=50
    )
    res = engine.evaluate(req)
    assert res.decision == "RATE_LIMIT"
    assert res.maximum_bandwidth_mbps == 10.0
    assert "UNKNOWN" in res.reason

def test_evaluate_custom_policy_override(setup_db):
    db = setup_db
    engine = PolicyEngine()
    req = PolicyEvalRequest(
        flow_id="flow_test_6",
        organisation_id="org_test_hq",
        application="CustomApp",
        application_class="Critical",
        link_id="link_chennai_cloud",
        link_utilisation_pct=50.0,
        service_priority=95
    )
    res = engine.evaluate(req, db=db)
    assert res.decision == "GUARANTEE_MINIMUM"
    assert res.minimum_bandwidth_mbps == 60.0
    assert "Custom organisation policy applied" in res.reason
