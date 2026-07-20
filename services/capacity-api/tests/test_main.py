from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoints_are_available():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_valid_recommendation_follows_the_contract():
    response = client.get("/api/v1/capacity/demo-workload/recommendation")

    assert response.status_code == 200
    body = response.json()
    assert body["stream"] == "capacity"
    assert body["target"] == "demo-workload"
    assert body["status"] == "normal"
    assert body["recommendation"] == {
        "replicas": 2,
        "action": "hold",
        "reason": "Forecast demand is within the current safe capacity.",
    }
    assert body["evidence"]["forecast_horizon_seconds"] == 60
    assert body["model_version"] == "capacity-stub-v1"
    assert body["timestamp"].endswith("Z")


def test_unknown_workload_returns_a_controlled_404():
    response = client.get("/api/v1/capacity/other-workload/recommendation")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "workload_not_found"


def test_invalid_workload_returns_a_controlled_422():
    response = client.get("/api/v1/capacity/Demo_Workload/recommendation")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_workload"


def test_metrics_expose_the_capacity_metric_catalogue():
    client.get("/api/v1/capacity/demo-workload/recommendation")
    response = client.get("/metrics")

    assert response.status_code == 200
    for metric in (
        "kubeaiops_capacity_api_requests_total",
        "kubeaiops_capacity_api_request_duration_seconds",
        "kubeaiops_capacity_predictions_total",
        "kubeaiops_capacity_forecast_requests_per_second",
        "kubeaiops_capacity_recommended_replicas",
        "kubeaiops_capacity_current_replicas",
        "kubeaiops_capacity_recommendation_gap",
        "kubeaiops_capacity_model_info",
    ):
        assert metric in response.text

    assert 'route="/api/v1/capacity/{workload}/recommendation"' in response.text
    assert 'workload="demo-workload"' in response.text
