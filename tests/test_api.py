import pytest
from fastapi.testclient import TestClient
from app.main import app, seed_database
from app.database import engine, Base

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    Base.metadata.create_all(bind=engine)
    seed_database()

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "HybridFlowGuard Policy Engine"

def test_failures_status_endpoint():
    response = client.get("/failures/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "fallback_active" in data

def test_get_organisations():
    headers = {
        "x-user-role": "admin",
        "x-organisation-id": "org_chennai_hq",
        "x-username": "admin_user"
    }
    response = client.get("/organisations", headers=headers)
    assert response.status_code == 200
    orgs = response.json()
    assert len(orgs) > 0

def test_get_links():
    response = client.get("/links")
    assert response.status_code == 200
    links = response.json()
    assert len(links) > 0

def test_get_applications():
    response = client.get("/applications")
    assert response.status_code == 200
    apps = response.json()
    assert len(apps) > 0

def test_get_policies():
    headers = {
        "x-user-role": "admin",
        "x-organisation-id": "org_chennai_hq",
        "x-username": "admin_user"
    }
    response = client.get("/policies", headers=headers)
    assert response.status_code == 200
    policies = response.json()
    assert isinstance(policies, list)

def test_create_and_update_policy():
    headers = {
        "x-user-role": "admin",
        "x-organisation-id": "org_chennai_hq",
        "x-username": "admin_user"
    }
    new_policy = {
        "organisation_id": "org_chennai_hq",
        "application": "TestAPIApp",
        "application_class": "Critical",
        "priority": 90,
        "minimum_bandwidth_mbps": 30.0,
        "maximum_bandwidth_mbps": 100.0,
        "action": "GUARANTEE_MINIMUM"
    }
    res_create = client.post("/policies", json=new_policy, headers=headers)
    assert res_create.status_code == 201
    pol_data = res_create.json()
    pol_id = pol_data["id"]
    assert pol_data["application"] == "TestAPIApp"

    # Update policy
    update_payload = {
        "minimum_bandwidth_mbps": 35.0,
        "priority": 95
    }
    res_update = client.put(f"/policies/{pol_id}", json=update_payload, headers=headers)
    assert res_update.status_code == 200
    updated_data = res_update.json()
    assert updated_data["minimum_bandwidth_mbps"] == 35.0

def test_evaluate_policy_endpoint():
    req_payload = {
        "flow_id": "flow_eval_test",
        "organisation_id": "org_chennai_hq",
        "application": "VoIP",
        "application_class": "Critical",
        "link_id": "link_chennai_cloud",
        "link_utilisation_pct": 97.0,
        "service_priority": 100
    }
    response = client.post("/policy/evaluate", json=req_payload)
    assert response.status_code == 200
    result = response.json()
    assert result["decision"] == "PRIORITISE"
    assert result["minimum_bandwidth_mbps"] == 40.0

def test_get_flows():
    headers = {
        "x-user-role": "admin",
        "x-organisation-id": "org_chennai_hq",
        "x-username": "admin_user"
    }
    response = client.get("/flows?limit=10", headers=headers)
    assert response.status_code == 200
    flows = response.json()
    assert isinstance(flows, list)

def test_experiments_run_endpoint():
    payload = {
        "scenario": "90% congestion",
        "num_flows": 20
    }
    response = client.post("/experiments/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "metrics_summary" in data
    assert "error_analysis" in data
    assert data["scenario"] == "90% congestion"

def test_experiments_results_endpoint():
    response = client.get("/experiments/results")
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
