from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ml" / "capacity" / "src"))
sys.path.insert(0, str(ROOT / "ml" / "capacity" / "scripts"))

from capacity_data.pipeline import DatasetValidationError, clean_rows, validate_rows
from extract_prometheus_metrics import align_series


def observation(scenario: str, timestamp: str = "2026-07-25T09:00:00Z") -> dict[str, str]:
    return {
        "timestamp": timestamp,
        "workload": "demo-workload",
        "requests_per_second": "12.0",
        "cpu_utilization_ratio": "0.35",
        "memory_working_set_bytes": "220000000",
        "p95_latency_seconds": "0.05",
        "error_ratio": "0.001",
        "replicas": "2",
        "scaling_event": "none",
        "scenario": scenario,
        "collection_interval_seconds": "30",
        "data_source": "test",
        "run_status": "passed",
    }


def all_scenarios() -> list[dict[str, str]]:
    return [
        observation("normal"),
        observation("progressive"),
        observation("spike"),
        observation("sustained"),
        observation("recovery"),
    ]


def test_clean_rows_forward_fills_only_within_a_series() -> None:
    first = observation("normal")
    second = observation("normal", "2026-07-25T09:00:30Z")
    second["p95_latency_seconds"] = ""

    result = clean_rows([second, first])

    assert result.filled_values == 1
    assert result.rows[1]["p95_latency_seconds"] == "0.05"
    assert result.rows[0]["timestamp"] == "2026-07-25T09:00:00Z"


def test_clean_rows_rejects_an_unfillable_first_value() -> None:
    row = observation("normal")
    row["requests_per_second"] = ""

    with pytest.raises(DatasetValidationError, match="cannot be forward-filled"):
        clean_rows([row])


def test_validate_rows_requires_all_scenarios_and_consistent_intervals() -> None:
    rows = all_scenarios()
    normal_second = observation("normal", "2026-07-25T09:01:00Z")
    rows.append(normal_second)

    with pytest.raises(DatasetValidationError, match="expected 30s interval"):
        validate_rows(rows)


def test_validate_rows_reports_a_complete_valid_dataset() -> None:
    report = validate_rows(all_scenarios())

    assert report["valid"] is True
    assert report["record_count"] == 5
    assert report["checks"]["replica_alignment"] == "passed"


def test_prometheus_series_are_aligned_and_summed() -> None:
    results = [
        {"values": [["1784970000", "1.25"], ["1784970030", "2"]]},
        {"values": [["1784970000", "0.75"]]},
    ]

    assert align_series(results) == {
        "2026-07-25T09:00:00Z": 2.0,
        "2026-07-25T09:00:30Z": 2.0,
    }
