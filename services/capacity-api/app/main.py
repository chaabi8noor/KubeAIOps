from datetime import datetime, timezone
import re
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from pydantic import BaseModel, Field

APP_VERSION = "0.1.0"
KNOWN_WORKLOAD = "demo-workload"
WORKLOAD_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
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

MODEL_INFO = Gauge(
    "kubeaiops_capacity_model_info",
    "Active model identity.",
    ["model_name", "model_version"],
)

MODEL_INFO.labels(
    model_name="capacity_stub",
    model_version="capacity-stub-v1",
).set(1)


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


@app.get("/")
def root():
    return {
        "service": "capacity-api",
        "version": APP_VERSION,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
    }


@app.get("/health/live")
def liveness():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    return {"status": "ok"}


@app.get(
    "/api/v1/capacity/{workload}/recommendation",
    response_model=CapacityRecommendationResponse,
)
def get_recommendation(workload: str):
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

    API_REQUESTS.labels(
        namespace="kubeaiops",
        service="capacity-api",
        method="GET",
        route="/api/v1/capacity/{workload}/recommendation",
        status="200",
    ).inc()

    return CapacityRecommendationResponse(
        stream="capacity",
        target=workload,
        status="normal",
        score=0.25,
        evidence=Evidence(
            current_requests_per_second=20.0,
            forecast_requests_per_second=25.0,
            current_replicas=2,
            cpu_utilization=0.35,
            forecast_horizon_seconds=60,
        ),
        recommendation=ReplicaRecommendation(
            replicas=2,
            action="hold",
            reason="Forecast demand is within the current safe capacity.",
        ),
        model_version="capacity-stub-v1",
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
