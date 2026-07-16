from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.1.0",
    }


def test_valid_recommendation():
    response = client.get(
        "/api/v1/capacity/demo-workload/recommendation"
    )

    assert response.status_code == 200

    body = response.json()
    assert body["stream"] == "capacity"
    assert body["target"] == "demo-workload"
    assert body["status"] == "normal"
    assert body["recommendation"]["action"] == "hold"
    assert body["recommendation"]["replicas"] == 2
    assert body["model_version"] == "capacity-stub-v1"


def test_unknown_workload_returns_404():
    response = client.get(
        "/api/v1/capacity/other-workload/recommendation"
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "workload_not_found"


def test_invalid_workload_returns_422():
    response = client.get(
        "/api/v1/capacity/Demo_Workload/recommendation"
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_workload"


def test_metrics_endpoint_exposes_capacity_metrics():
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "kubeaiops_capacity_model_info" in response.text
