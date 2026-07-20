"""Contract-aligned Capacity API stub for the Week 1-2 vertical slice."""

from datetime import datetime, timezone
import os
import re
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
NAMESPACE = os.getenv("NAMESPACE", "kubeaiops")
SERVICE_NAME = "capacity-api"
KNOWN_WORKLOAD = os.getenv("KNOWN_WORKLOAD", "demo-workload")
MODEL_NAME = os.getenv("MODEL_NAME", "capacity_stub")
MODEL_VERSION = os.getenv("MODEL_VERSION", "capacity-stub-v1")
WORKLOAD_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def configured_positive_int(name: str, default: int) -> int:
    """Read a positive integer without allowing an invalid local config to crash startup."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


FORECAST_HORIZON_SECONDS = configured_positive_int("FORECAST_HORIZON_SECONDS", 60)
MIN_REPLICAS = configured_positive_int("MIN_REPLICAS", 1)
MAX_REPLICAS = max(
    MIN_REPLICAS,
    configured_positive_int("MAX_REPLICAS", 5),
)

app = FastAPI(
    title="KubeAIOps Capacity API",
    version=APP_VERSION,
)

API_REQUESTS = Counter(
    "kubeaiops_capacity_api_requests",
    "Total recommendation API requests.",
    ["namespace", "service", "method", "route", "status"],
)
API_REQUEST_DURATION = Histogram(
    "kubeaiops_capacity_api_request_duration_seconds",
    "Recommendation API response-time distribution in seconds.",
    ["namespace", "service", "method", "route", "status"],
)
PREDICTIONS = Counter(
    "kubeaiops_capacity_predictions",
    "Successful capacity forecasts produced.",
    ["namespace", "workload", "model_version"],
)
PREDICTION_FAILURES = Counter(
    "kubeaiops_capacity_prediction_failures",
    "Capacity prediction failures by controlled reason.",
    ["namespace", "workload", "model_version", "reason"],
)
FORECAST_REQUESTS_PER_SECOND = Gauge(
    "kubeaiops_capacity_forecast_requests_per_second",
    "Forecast workload request rate in requests per second.",
    ["namespace", "workload", "model_version"],
)
RECOMMENDED_REPLICAS = Gauge(
    "kubeaiops_capacity_recommended_replicas",
    "Replica count recommended by the capacity policy.",
    ["namespace", "workload", "model_version"],
)
CURRENT_REPLICAS = Gauge(
    "kubeaiops_capacity_current_replicas",
    "Current available replicas used by the capacity policy.",
    ["namespace", "workload"],
)
RECOMMENDATION_GAP = Gauge(
    "kubeaiops_capacity_recommendation_gap",
    "Recommended replicas minus current available replicas.",
    ["namespace", "workload", "model_version"],
)
METRICS_SOURCE_FAILURES = Counter(
    "kubeaiops_capacity_metrics_source_failures",
    "Failures while retrieving workload metrics.",
    ["namespace", "workload", "reason"],
)
MODEL_INFO = Gauge(
    "kubeaiops_capacity_model_info",
    "Active model identity.",
    ["model_name", "model_version"],
)
MODEL_INFO.labels(model_name=MODEL_NAME, model_version=MODEL_VERSION).set(1)


class Evidence(BaseModel):
    current_requests_per_second: float = Field(ge=0)
    forecast_requests_per_second: float = Field(ge=0)
    current_replicas: int = Field(ge=1)
    cpu_utilization: float = Field(ge=0, le=1)
    forecast_horizon_seconds: int = Field(gt=0)


class ReplicaRecommendation(BaseModel):
    replicas: int = Field(ge=1)
    action: Literal["hold", "scale_up", "scale_down", "insufficient_data"]
    reason: str


class CapacityRecommendationResponse(BaseModel):
    stream: Literal["capacity"]
    target: str
    status: Literal["normal", "warning", "critical", "unknown"]
    score: float = Field(ge=0, le=1)
    evidence: Evidence
    recommendation: ReplicaRecommendation
    model_version: str
    timestamp: datetime


def record_api_request(started_at: float, status_code: int) -> None:
    """Record bounded labels for every recommendation request outcome."""
    labels = {
        "namespace": NAMESPACE,
        "service": SERVICE_NAME,
        "method": "GET",
        "route": "/api/v1/capacity/{workload}/recommendation",
        "status": str(status_code),
    }
    API_REQUESTS.labels(**labels).inc()
    API_REQUEST_DURATION.labels(**labels).observe(perf_counter() - started_at)


def recommendation_for(workload: str) -> CapacityRecommendationResponse:
    """Produce a stable, bounded stub decision until the forecast model is integrated."""
    current_replicas = 2
    forecast_requests_per_second = 25.0
    recommended_replicas = min(max(current_replicas, MIN_REPLICAS), MAX_REPLICAS)

    labels = {
        "namespace": NAMESPACE,
        "workload": workload,
        "model_version": MODEL_VERSION,
    }
    PREDICTIONS.labels(**labels).inc()
    FORECAST_REQUESTS_PER_SECOND.labels(**labels).set(forecast_requests_per_second)
    RECOMMENDED_REPLICAS.labels(**labels).set(recommended_replicas)
    CURRENT_REPLICAS.labels(namespace=NAMESPACE, workload=workload).set(current_replicas)
    RECOMMENDATION_GAP.labels(**labels).set(recommended_replicas - current_replicas)

    return CapacityRecommendationResponse(
        stream="capacity",
        target=workload,
        status="normal",
        score=0.25,
        evidence=Evidence(
            current_requests_per_second=20.0,
            forecast_requests_per_second=forecast_requests_per_second,
            current_replicas=current_replicas,
            cpu_utilization=0.35,
            forecast_horizon_seconds=FORECAST_HORIZON_SECONDS,
        ),
        recommendation=ReplicaRecommendation(
            replicas=recommended_replicas,
            action="hold",
            reason="Forecast demand is within the current safe capacity.",
        ),
        model_version=MODEL_VERSION,
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"service": SERVICE_NAME, "version": APP_VERSION}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/v1/capacity/{workload}/recommendation",
    response_model=CapacityRecommendationResponse,
)
def get_recommendation(workload: str) -> CapacityRecommendationResponse:
    started_at = perf_counter()
    try:
        if not WORKLOAD_PATTERN.fullmatch(workload):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "invalid_workload",
                    "message": "Workload must be a lowercase DNS-label-style name.",
                    "target": workload,
                },
            )

        if workload != KNOWN_WORKLOAD:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "workload_not_found",
                    "message": "No capacity configuration exists for this workload.",
                    "target": workload,
                },
            )

        response = recommendation_for(workload)
    except HTTPException as error:
        record_api_request(started_at, error.status_code)
        raise
    except Exception as error:  # Defensive boundary for the future model integration.
        PREDICTION_FAILURES.labels(
            namespace=NAMESPACE,
            workload=workload if WORKLOAD_PATTERN.fullmatch(workload) else "invalid",
            model_version=MODEL_VERSION,
            reason="internal_prediction_error",
        ).inc()
        record_api_request(started_at, 500)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "prediction_failed",
                "message": "The capacity recommendation could not be produced.",
            },
        ) from error

    record_api_request(started_at, 200)
    return response


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
