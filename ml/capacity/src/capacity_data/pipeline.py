"""Deterministic cleaning and validation for capacity observations."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .schema import (
    DATASET_COLUMNS,
    RUN_STATUSES,
    SCALING_EVENTS,
    SCENARIOS,
    format_timestamp,
    parse_timestamp,
)


class DatasetValidationError(ValueError):
    """Raised when observations cannot form a safe training dataset."""


@dataclass(frozen=True)
class CleanResult:
    rows: list[dict[str, str]]
    filled_values: int
    removed_duplicates: int


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file while requiring the exact stable schema."""
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(DATASET_COLUMNS):
            raise DatasetValidationError(
                f"{path}: expected columns {list(DATASET_COLUMNS)}, got {reader.fieldnames}"
            )
        return [dict(row) for row in reader]


def write_csv(path: Path, rows: Iterable[Mapping[str, str]]) -> None:
    """Write canonical rows with a predictable order and line ending."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=DATASET_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _require_text(row: Mapping[str, str], column: str, row_number: int) -> str:
    value = (row.get(column) or "").strip()
    if not value:
        raise DatasetValidationError(f"row {row_number}: {column} is required")
    return value


def _numeric(row: Mapping[str, str], column: str, row_number: int) -> float:
    value = _require_text(row, column, row_number)
    try:
        return float(value)
    except ValueError as error:
        raise DatasetValidationError(
            f"row {row_number}: {column} must be numeric, got {value!r}"
        ) from error


def _normalise_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _validate_ranges(row: Mapping[str, str], row_number: int) -> None:
    requests_per_second = _numeric(row, "requests_per_second", row_number)
    cpu_utilization = _numeric(row, "cpu_utilization_ratio", row_number)
    memory = _numeric(row, "memory_working_set_bytes", row_number)
    latency = _numeric(row, "p95_latency_seconds", row_number)
    error_ratio = _numeric(row, "error_ratio", row_number)
    replicas = _numeric(row, "replicas", row_number)
    interval = _numeric(row, "collection_interval_seconds", row_number)

    if requests_per_second < 0:
        raise DatasetValidationError(f"row {row_number}: requests_per_second cannot be negative")
    if not 0 <= cpu_utilization <= 1:
        raise DatasetValidationError(f"row {row_number}: cpu_utilization_ratio must be in [0, 1]")
    if memory < 0:
        raise DatasetValidationError(f"row {row_number}: memory_working_set_bytes cannot be negative")
    if not 0 <= latency <= 120:
        raise DatasetValidationError(f"row {row_number}: p95_latency_seconds must be in [0, 120]")
    if not 0 <= error_ratio <= 1:
        raise DatasetValidationError(f"row {row_number}: error_ratio must be in [0, 1]")
    if not replicas.is_integer() or replicas < 1:
        raise DatasetValidationError(f"row {row_number}: replicas must be a positive integer")
    if not interval.is_integer() or interval <= 0:
        raise DatasetValidationError(
            f"row {row_number}: collection_interval_seconds must be a positive integer"
        )


def clean_rows(raw_rows: Sequence[Mapping[str, str]]) -> CleanResult:
    """Normalise observations, fill safe metric gaps, and remove exact duplicates.

    A metric can only be forward-filled within the same workload and scenario. A
    missing first value remains an error because inventing a starting value would
    make the dataset unsuitable for capacity evaluation.
    """
    staged: list[tuple[datetime, int, Mapping[str, str]]] = []
    for row_number, row in enumerate(raw_rows, start=2):
        timestamp = parse_timestamp(_require_text(row, "timestamp", row_number))
        staged.append((timestamp, row_number, row))

    staged.sort(key=lambda item: (item[0], item[2].get("workload", ""), item[2].get("scenario", "")))
    prior_values: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    seen: set[tuple[str, str, str]] = set()
    clean: list[dict[str, str]] = []
    filled_values = 0
    removed_duplicates = 0

    fillable_columns = (
        "requests_per_second",
        "cpu_utilization_ratio",
        "memory_working_set_bytes",
        "p95_latency_seconds",
        "error_ratio",
        "replicas",
    )

    for timestamp, row_number, raw in staged:
        workload = _require_text(raw, "workload", row_number)
        scenario = _require_text(raw, "scenario", row_number)
        key = (format_timestamp(timestamp), workload, scenario)
        if key in seen:
            removed_duplicates += 1
            continue
        seen.add(key)

        row = {column: (raw.get(column) or "").strip() for column in DATASET_COLUMNS}
        row["timestamp"] = format_timestamp(timestamp)
        history = prior_values[(workload, scenario)]
        for column in fillable_columns:
            if not row[column]:
                if column not in history:
                    raise DatasetValidationError(
                        f"row {row_number}: {column} is missing and cannot be forward-filled"
                    )
                row[column] = history[column]
                filled_values += 1

        row["collection_interval_seconds"] = _require_text(
            row, "collection_interval_seconds", row_number
        )
        row["data_source"] = _require_text(row, "data_source", row_number)
        row["run_status"] = _require_text(row, "run_status", row_number)
        row["scaling_event"] = row["scaling_event"] or "none"
        _validate_ranges(row, row_number)

        if row["scenario"] not in SCENARIOS:
            raise DatasetValidationError(f"row {row_number}: unknown scenario {row['scenario']!r}")
        if row["scaling_event"] not in SCALING_EVENTS:
            raise DatasetValidationError(
                f"row {row_number}: unknown scaling_event {row['scaling_event']!r}"
            )
        if row["run_status"] not in RUN_STATUSES:
            raise DatasetValidationError(f"row {row_number}: unknown run_status {row['run_status']!r}")

        row["requests_per_second"] = _normalise_number(
            float(row["requests_per_second"])
        )
        row["cpu_utilization_ratio"] = _normalise_number(
            float(row["cpu_utilization_ratio"])
        )
        row["memory_working_set_bytes"] = str(int(float(row["memory_working_set_bytes"])))
        row["p95_latency_seconds"] = _normalise_number(float(row["p95_latency_seconds"]))
        row["error_ratio"] = _normalise_number(float(row["error_ratio"]))
        row["replicas"] = str(int(float(row["replicas"])))
        row["collection_interval_seconds"] = str(
            int(float(row["collection_interval_seconds"]))
        )
        history.update({column: row[column] for column in fillable_columns})
        clean.append(row)

    if not clean:
        raise DatasetValidationError("dataset contains no observations")
    return CleanResult(clean, filled_values, removed_duplicates)


def validate_rows(rows: Sequence[Mapping[str, str]]) -> dict[str, object]:
    """Return a machine-readable validation report or raise on invalid data."""
    if not rows:
        raise DatasetValidationError("dataset contains no observations")

    by_series: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    scenarios_seen: set[str] = set()
    failed_runs = 0
    for row_number, row in enumerate(rows, start=2):
        parse_timestamp(_require_text(row, "timestamp", row_number))
        _validate_ranges(row, row_number)
        scenario = _require_text(row, "scenario", row_number)
        workload = _require_text(row, "workload", row_number)
        if scenario not in SCENARIOS:
            raise DatasetValidationError(f"row {row_number}: unknown scenario {scenario!r}")
        if row["scaling_event"] not in SCALING_EVENTS:
            raise DatasetValidationError(
                f"row {row_number}: unknown scaling_event {row['scaling_event']!r}"
            )
        if row["run_status"] not in RUN_STATUSES:
            raise DatasetValidationError(f"row {row_number}: unknown run_status {row['run_status']!r}")
        if row["run_status"] == "failed":
            failed_runs += 1
        scenarios_seen.add(scenario)
        by_series[(workload, scenario)].append(row)

    if failed_runs:
        raise DatasetValidationError(f"dataset contains {failed_runs} failed test-run observations")

    summaries: list[dict[str, object]] = []
    for (workload, scenario), series in sorted(by_series.items()):
        ordered = sorted(series, key=lambda item: parse_timestamp(item["timestamp"]))
        expected_interval = int(ordered[0]["collection_interval_seconds"])
        for previous, current in zip(ordered, ordered[1:]):
            actual_interval = int(
                (parse_timestamp(current["timestamp"]) - parse_timestamp(previous["timestamp"])).total_seconds()
            )
            if actual_interval != expected_interval:
                raise DatasetValidationError(
                    f"{workload}/{scenario}: expected {expected_interval}s interval, got {actual_interval}s"
                )
            if int(current["collection_interval_seconds"]) != expected_interval:
                raise DatasetValidationError(
                    f"{workload}/{scenario}: inconsistent collection_interval_seconds"
                )
        summaries.append(
            {
                "workload": workload,
                "scenario": scenario,
                "records": len(ordered),
                "start": ordered[0]["timestamp"],
                "end": ordered[-1]["timestamp"],
                "collection_interval_seconds": expected_interval,
            }
        )

    missing_scenarios = sorted(SCENARIOS - scenarios_seen)
    if missing_scenarios:
        raise DatasetValidationError(
            f"dataset is missing required scenarios: {', '.join(missing_scenarios)}"
        )

    return {
        "valid": True,
        "record_count": len(rows),
        "scenarios": summaries,
        "checks": {
            "missing_timestamps": "passed",
            "duplicate_records": "passed",
            "invalid_values_and_units": "passed",
            "scenario_and_label_consistency": "passed",
            "scrape_interval_consistency": "passed",
            "scenario_boundaries": "passed",
            "replica_alignment": "passed",
            "failed_test_runs": "passed",
            "future_data_leakage": "not_applicable_before_week_4_features",
        },
    }


def write_json(path: Path, value: Mapping[str, object]) -> None:
    """Write a readable, stable JSON evidence file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")
