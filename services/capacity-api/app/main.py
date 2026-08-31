"""Capacity API backed by the frozen primary forecasting model."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from pydantic import BaseModel, Field

from .model_runtime import (
    FeatureSourceError,
    FeatureValidationError,
    ModelArtifactError,
    PolicyConfigurationError,
    RuntimeInput,
    load_model_runtime,
)


APP_VERSION = os.getenv("APP_VERSION", "0.2.0")
NAMESPACE = os.getenv("NAMESPACE", "kubeaiops")
SERVICE_NAME = "capacity-api"
KNOWN_WORKLOAD = os.getenv("KNOWN_WORKLOAD", "demo-workload")
MODEL_PATH = os.getenv("MODEL_PATH", str(Path(__file__).resolve().parents[1] / "models"))
WORKLOAD_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def configured_positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


FORECAST_HORIZON_SECONDS = configured_positive_int("FORECAST_HORIZON_SECONDS", 60)

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
RECOMMENDATION_LEVELS = Counter(
    "kubeaiops_capacity_recommendations",
    "Capacity recommendations by action.",
    ["namespace", "workload", "model_version", "action"],
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
API_HEALTH = Gauge(
    "kubeaiops_capacity_api_health",
    "Whether the Capacity API completed startup validation.",
    ["namespace", "service"],
)
MODEL_INFO = Gauge(
    "kubeaiops_capacity_model_info",
    "Active model identity.",
    ["model_name", "model_version"],
)


class Evidence(BaseModel):
    current_requests_per_second: float = Field(ge=0)
    forecast_requests_per_second: float = Field(ge=0)
    current_replicas: int = Field(ge=1)
    cpu_utilization: float = Field(ge=0, le=1)
    forecast_horizon_seconds: int = Field(gt=0)


class ReplicaRecommendation(BaseModel):
    replicas: int = Field(ge=1)
    action: Literal["hold", "scale_up", "scale_down"]
    reason: str


class CapacityRecommendationResponse(BaseModel):
    stream: Literal["capacity"]
    target: str
    status: Literal["normal", "warning", "critical"]
    score: float = Field(ge=0, le=1)
    evidence: Evidence
    recommendation: ReplicaRecommendation
    model_version: str
    timestamp: datetime


def record_api_request(started_at: float, status_code: int) -> None:
    labels = {
        "namespace": NAMESPACE,
        "service": SERVICE_NAME,
        "method": "GET",
        "route": "/api/v1/capacity/{workload}/recommendation",
        "status": str(status_code),
    }
    API_REQUESTS.labels(**labels).inc()
    API_REQUEST_DURATION.labels(**labels).observe(perf_counter() - started_at)


@asynccontextmanager
async def lifespan(application: FastAPI):
    runtime = load_model_runtime(Path(MODEL_PATH))
    application.state.runtime = runtime
    MODEL_INFO.labels(model_name="capacity-primary", model_version=runtime.model_version).set(1)
    API_HEALTH.labels(namespace=NAMESPACE, service=SERVICE_NAME).set(1)
    yield
    API_HEALTH.labels(namespace=NAMESPACE, service=SERVICE_NAME).set(0)


app = FastAPI(title="KubeAIOps Capacity API", version=APP_VERSION, lifespan=lifespan)


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
def readiness(request: Request) -> dict[str, str]:
    if not hasattr(request.app.state, "runtime"):
        raise HTTPException(status_code=503, detail={"code": "model_not_ready"})
    return {"status": "ok"}


def recommendation_for(request: Request, workload: str) -> CapacityRecommendationResponse:
    feature_input = RuntimeInput.from_environment()
    runtime = request.app.state.runtime
    forecast, replicas, action, reason = runtime.recommend(feature_input)
    labels = {
        "namespace": NAMESPACE,
        "workload": workload,
        "model_version": runtime.model_version,
    }
    PREDICTIONS.labels(**labels).inc()
    RECOMMENDATION_LEVELS.labels(**labels, action=action).inc()
    FORECAST_REQUESTS_PER_SECOND.labels(**labels).set(forecast)
    RECOMMENDED_REPLICAS.labels(**labels).set(replicas)
    CURRENT_REPLICAS.labels(namespace=NAMESPACE, workload=workload).set(
        feature_input.current_replicas
    )
    RECOMMENDATION_GAP.labels(**labels).set(replicas - feature_input.current_replicas)
    pressure = forecast / max(
        1.0, feature_input.current_replicas * runtime.policy.effective_capacity_per_replica
    )
    status = "critical" if pressure >= 1.25 else "warning" if pressure >= 1 else "normal"
    return CapacityRecommendationResponse(
        stream="capacity",
        target=workload,
        status=status,
        score=min(1.0, pressure),
        evidence=Evidence(
            current_requests_per_second=feature_input.current_requests_per_second,
            forecast_requests_per_second=forecast,
            current_replicas=feature_input.current_replicas,
            cpu_utilization=feature_input.cpu_utilization_ratio,
            forecast_horizon_seconds=FORECAST_HORIZON_SECONDS,
        ),
        recommendation=ReplicaRecommendation(replicas=replicas, action=action, reason=reason),
        model_version=runtime.model_version,
        timestamp=datetime.now(timezone.utc),
    )


@app.get(
    "/api/v1/capacity/{workload}/recommendation",
    response_model=CapacityRecommendationResponse,
)
def get_recommendation(request: Request, workload: str) -> CapacityRecommendationResponse:
    started_at = perf_counter()
    model_version = getattr(getattr(request.app.state, "runtime", None), "model_version", "unavailable")
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
        response = recommendation_for(request, workload)
    except HTTPException as error:
        record_api_request(started_at, error.status_code)
        raise
    except FeatureSourceError as error:
        METRICS_SOURCE_FAILURES.labels(
            namespace=NAMESPACE, workload=workload, reason="source_unavailable"
        ).inc()
        PREDICTION_FAILURES.labels(
            namespace=NAMESPACE,
            workload=workload,
            model_version=model_version,
            reason="metrics_source_unavailable",
        ).inc()
        record_api_request(started_at, 503)
        raise HTTPException(
            status_code=503,
            detail={"code": "metrics_source_unavailable", "message": str(error)},
        ) from error
    except FeatureValidationError as error:
        PREDICTION_FAILURES.labels(
            namespace=NAMESPACE,
            workload=workload,
            model_version=model_version,
            reason="invalid_feature_values",
        ).inc()
        record_api_request(started_at, 422)
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_feature_values", "message": str(error)},
        ) from error
    except (ModelArtifactError, PolicyConfigurationError) as error:
        PREDICTION_FAILURES.labels(
            namespace=NAMESPACE,
            workload=workload,
            model_version=model_version,
            reason="runtime_configuration_error",
        ).inc()
        record_api_request(started_at, 500)
        raise HTTPException(
            status_code=500,
            detail={"code": "prediction_runtime_error", "message": "Model runtime is unavailable."},
        ) from error
    except Exception as error:
        PREDICTION_FAILURES.labels(
            namespace=NAMESPACE,
            workload=workload,
            model_version=model_version,
            reason="prediction_failed",
        ).inc()
        record_api_request(started_at, 500)
        raise HTTPException(
            status_code=500,
            detail={"code": "prediction_failed", "message": "The capacity recommendation could not be produced."},
        ) from error
    record_api_request(started_at, 200)
    return response


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
