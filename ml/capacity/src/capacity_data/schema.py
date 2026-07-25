"""Stable schema definitions for the capacity-observation dataset."""

from __future__ import annotations

from datetime import datetime, timezone


SCHEMA_VERSION = "1.0.0"

DATASET_COLUMNS = (
    "timestamp",
    "workload",
    "requests_per_second",
    "cpu_utilization_ratio",
    "memory_working_set_bytes",
    "p95_latency_seconds",
    "error_ratio",
    "replicas",
    "scaling_event",
    "scenario",
    "collection_interval_seconds",
    "data_source",
    "run_status",
)

NUMERIC_COLUMNS = (
    "requests_per_second",
    "cpu_utilization_ratio",
    "memory_working_set_bytes",
    "p95_latency_seconds",
    "error_ratio",
    "replicas",
    "collection_interval_seconds",
)

SCENARIOS = frozenset({"normal", "progressive", "spike", "sustained", "recovery"})
SCALING_EVENTS = frozenset({"none", "scale_up", "scale_down", "pod_replacement"})
RUN_STATUSES = frozenset({"passed", "failed"})

UNITS = {
    "timestamp": "RFC3339 UTC",
    "requests_per_second": "requests/second",
    "cpu_utilization_ratio": "ratio (0..1)",
    "memory_working_set_bytes": "bytes",
    "p95_latency_seconds": "seconds",
    "error_ratio": "ratio (0..1)",
    "replicas": "count",
    "collection_interval_seconds": "seconds",
}


def parse_timestamp(value: str) -> datetime:
    """Parse an RFC3339 timestamp and normalise it to UTC."""
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    parsed = datetime.fromisoformat(candidate)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def format_timestamp(value: datetime) -> str:
    """Render a datetime in the one representation used by this dataset."""
    normalised = value.astimezone(timezone.utc).replace(microsecond=0)
    return normalised.isoformat().replace("+00:00", "Z")
