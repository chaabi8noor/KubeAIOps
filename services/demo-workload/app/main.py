import time

from fastapi import FastAPI, Query, Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

APP_VERSION = "0.1.0"
NAMESPACE = "kubeaiops"
SERVICE_NAME = "demo-workload"
WORKLOAD_NAME = "demo-workload"
ALLOWED_SCENARIOS = {
    "normal",
    "progressive",
    "spike",
    "sustained",
    "recovery",
}

app = FastAPI(
    title="KubeAIOps Demo Workload",
    version=APP_VERSION,
)

WORKLOAD_REQUESTS = Counter(
    "kubeaiops_workload_requests",
    "Total requests served by the demo workload.",
    ["namespace", "service", "workload", "method", "route", "status", "scenario"],
)
WORKLOAD_REQUEST_DURATION = Histogram(
    "kubeaiops_workload_request_duration_seconds",
    "Demo workload request latency in seconds.",
    ["namespace", "service", "workload", "method", "route", "status", "scenario"],
)
WORKLOAD_ERRORS = Counter(
    "kubeaiops_workload_errors",
    "Request failures served by the demo workload.",
    ["namespace", "service", "workload", "scenario"],
)


def scenario_from(request: Request) -> str:
    scenario = request.headers.get("X-KubeAIOps-Scenario", "normal")
    return scenario if scenario in ALLOWED_SCENARIOS else "normal"


def route_label(request: Request) -> str:
    known_routes = {"/", "/health", "/health/live", "/health/ready", "/work"}
    return request.url.path if request.url.path in known_routes else "other"


@app.middleware("http")
async def capture_workload_metrics(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)

    started_at = time.perf_counter()
    scenario = scenario_from(request)
    response = await call_next(request)
    duration_seconds = time.perf_counter() - started_at
    labels = {
        "namespace": NAMESPACE,
        "service": SERVICE_NAME,
        "workload": WORKLOAD_NAME,
        "method": request.method,
        "route": route_label(request),
        "status": str(response.status_code),
        "scenario": scenario,
    }

    WORKLOAD_REQUESTS.labels(**labels).inc()
    WORKLOAD_REQUEST_DURATION.labels(**labels).observe(duration_seconds)

    if response.status_code >= 400:
        WORKLOAD_ERRORS.labels(
            namespace=NAMESPACE,
            service=SERVICE_NAME,
            workload=WORKLOAD_NAME,
            scenario=scenario,
        ).inc()

    return response


@app.get("/")
def root():
    return {
        "service": SERVICE_NAME,
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


@app.get("/work")
def work(
    iterations: int = Query(default=5_000, ge=0, le=250_000),
    delay_ms: int = Query(default=0, ge=0, le=200),
):
    """Perform bounded CPU and optional delay work for repeatable load tests."""
    checksum = 0
    for value in range(iterations):
        checksum = (checksum + value * value) % 97_409

    if delay_ms:
        time.sleep(delay_ms / 1_000)

    return {
        "workload": WORKLOAD_NAME,
        "iterations": iterations,
        "delay_ms": delay_ms,
        "checksum": checksum,
    }


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
