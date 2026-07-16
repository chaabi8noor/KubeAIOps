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


def test_work_returns_a_bounded_work_result():
    response = client.get("/work?iterations=100&delay_ms=0")

    assert response.status_code == 200
    assert response.json()["workload"] == "demo-workload"
    assert response.json()["iterations"] == 100


def test_work_rejects_an_unsafe_iteration_count():
    response = client.get("/work?iterations=-1")

    assert response.status_code == 422


def test_metrics_include_the_workload_contract_series():
    response = client.get(
        "/work?iterations=10",
        headers={"X-KubeAIOps-Scenario": "progressive"},
    )
    assert response.status_code == 200

    metrics = client.get("/metrics")

    assert metrics.status_code == 200
    assert "kubeaiops_workload_requests_total" in metrics.text
    assert "kubeaiops_workload_request_duration_seconds" in metrics.text
    assert 'scenario="progressive"' in metrics.text
