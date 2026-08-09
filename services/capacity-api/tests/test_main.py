from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.model_runtime import ModelArtifactError, load_model_runtime


def test_health_endpoints_are_available_after_model_startup_validation():
    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "version": "0.2.0"}
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ok"}


def test_primary_model_recommendation_follows_the_contract(monkeypatch):
    monkeypatch.setenv("CAPACITY_CURRENT_REQUESTS_PER_SECOND", "12.124")
    monkeypatch.setenv("CAPACITY_REQUEST_RATE_LAG_1", "12.065")
    monkeypatch.setenv("CAPACITY_REQUEST_RATE_ROLLING_MEAN", "12.063")
    monkeypatch.setenv("CAPACITY_CPU_UTILIZATION", "0.362")
    monkeypatch.setenv("CAPACITY_P95_LATENCY_SECONDS", "0.048")
    monkeypatch.setenv("CAPACITY_ERROR_RATIO", "0.001")
    monkeypatch.setenv("CAPACITY_CURRENT_REPLICAS", "2")
    monkeypatch.setenv("CAPACITY_SCENARIO", "normal")
    with TestClient(app) as client:
        response = client.get("/api/v1/capacity/demo-workload/recommendation")

    assert response.status_code == 200
    body = response.json()
    assert body["stream"] == "capacity"
    assert body["target"] == "demo-workload"
    assert body["status"] == "normal"
    assert body["recommendation"] == {
        "replicas": 1,
        "action": "scale_down",
        "reason": "Predicted demand remains below the guarded downscale threshold.",
    }
    assert body["evidence"]["current_requests_per_second"] == 12.124
    assert body["evidence"]["forecast_requests_per_second"] == pytest.approx(12.194)
    assert body["evidence"]["forecast_horizon_seconds"] == 60
    assert body["model_version"] == "capacity-primary-v1"
    assert body["timestamp"].endswith("Z")


def test_unknown_workload_returns_a_controlled_404():
    with TestClient(app) as client:
        response = client.get("/api/v1/capacity/other-workload/recommendation")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "workload_not_found"


def test_invalid_workload_returns_a_controlled_422():
    with TestClient(app) as client:
        response = client.get("/api/v1/capacity/Demo_Workload/recommendation")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_workload"


def test_invalid_runtime_feature_values_return_a_controlled_422(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setenv("CAPACITY_CURRENT_REQUESTS_PER_SECOND", "nan")
        response = client.get("/api/v1/capacity/demo-workload/recommendation")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_feature_values"


def test_metrics_source_failure_returns_a_controlled_503(monkeypatch):
    with TestClient(app) as client:
        monkeypatch.setenv("CAPACITY_METRICS_MODE", "unavailable")
        response = client.get("/api/v1/capacity/demo-workload/recommendation")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "metrics_source_unavailable"


def test_model_loader_rejects_missing_artifacts(tmp_path: Path):
    with pytest.raises(ModelArtifactError, match="exactly one frozen model"):
        load_model_runtime(tmp_path)


def test_metrics_expose_the_capacity_metric_catalogue():
    with TestClient(app) as client:
        client.get("/api/v1/capacity/demo-workload/recommendation")
        response = client.get("/metrics")

    assert response.status_code == 200
    for metric in (
        "kubeaiops_capacity_api_requests_total",
        "kubeaiops_capacity_api_request_duration_seconds",
        "kubeaiops_capacity_predictions_total",
        "kubeaiops_capacity_prediction_failures_total",
        "kubeaiops_capacity_recommendations_total",
        "kubeaiops_capacity_forecast_requests_per_second",
        "kubeaiops_capacity_recommended_replicas",
        "kubeaiops_capacity_current_replicas",
        "kubeaiops_capacity_recommendation_gap",
        "kubeaiops_capacity_api_health",
        "kubeaiops_capacity_model_info",
    ):
        assert metric in response.text

    assert 'route="/api/v1/capacity/{workload}/recommendation"' in response.text
    assert 'workload="demo-workload"' in response.text
    assert 'model_version="capacity-primary-v1"' in response.text
