"""Convert validated capacity observations into leakage-safe feature rows."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from capacity_data.schema import parse_timestamp


FEATURE_COLUMNS = (
    "timestamp",
    "target_timestamp",
    "workload",
    "scenario",
    "current_requests_per_second",
    "request_rate_lag_1",
    "request_rate_rolling_mean",
    "cpu_utilization_ratio",
    "memory_working_set_bytes",
    "p95_latency_seconds",
    "error_ratio",
    "current_replicas",
    "scaling_event",
    "target_requests_per_second",
    "split",
)


class FeatureConfigurationError(ValueError):
    """Raised when a feature-pipeline configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class FeatureConfig:
    version: str
    horizon_steps: int
    rolling_window_steps: int
    train_fraction: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "FeatureConfig":
        try:
            config = cls(
                version=str(value["version"]),
                horizon_steps=int(value["horizon_steps"]),
                rolling_window_steps=int(value["rolling_window_steps"]),
                train_fraction=float(value["train_fraction"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise FeatureConfigurationError("Invalid feature configuration") from error
        if not config.version:
            raise FeatureConfigurationError("Feature configuration requires a version")
        if config.horizon_steps < 1:
            raise FeatureConfigurationError("horizon_steps must be positive")
        if config.rolling_window_steps < 2:
            raise FeatureConfigurationError("rolling_window_steps must be at least 2")
        if not 0 < config.train_fraction < 1:
            raise FeatureConfigurationError("train_fraction must be between 0 and 1")
        return config


def _number(row: Mapping[str, str], column: str) -> float:
    try:
        return float(row[column])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid {column!r} in feature input") from error


def _format_number(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def build_feature_rows(
    observations: Sequence[Mapping[str, str]], config: FeatureConfig
) -> list[dict[str, str]]:
    """Build chronological feature rows without crossing scenario boundaries.

    Each feature row uses data at or before its `timestamp`; its forecast target
    is explicitly stored at the later `target_timestamp`. Splits are based on
    that target timestamp, which prevents future targets from entering training.
    """
    groups: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for observation in observations:
        groups[(observation["workload"], observation["scenario"])].append(observation)

    feature_rows: list[dict[str, str]] = []
    for (workload, scenario), series in sorted(groups.items()):
        ordered = sorted(series, key=lambda row: parse_timestamp(row["timestamp"]))
        first_index = config.rolling_window_steps - 1
        last_index = len(ordered) - config.horizon_steps
        for index in range(first_index, last_index):
            current = ordered[index]
            history = ordered[index - config.rolling_window_steps + 1 : index + 1]
            target = ordered[index + config.horizon_steps]
            rate_history = [_number(row, "requests_per_second") for row in history]
            feature_rows.append(
                {
                    "timestamp": current["timestamp"],
                    "target_timestamp": target["timestamp"],
                    "workload": workload,
                    "scenario": scenario,
                    "current_requests_per_second": _format_number(rate_history[-1]),
                    "request_rate_lag_1": _format_number(rate_history[-2]),
                    "request_rate_rolling_mean": _format_number(
                        sum(rate_history) / len(rate_history)
                    ),
                    "cpu_utilization_ratio": _format_number(
                        _number(current, "cpu_utilization_ratio")
                    ),
                    "memory_working_set_bytes": str(
                        int(_number(current, "memory_working_set_bytes"))
                    ),
                    "p95_latency_seconds": _format_number(
                        _number(current, "p95_latency_seconds")
                    ),
                    "error_ratio": _format_number(_number(current, "error_ratio")),
                    "current_replicas": str(int(_number(current, "replicas"))),
                    "scaling_event": current["scaling_event"],
                    "target_requests_per_second": _format_number(
                        _number(target, "requests_per_second")
                    ),
                    "split": "",
                }
            )

    if not feature_rows:
        raise ValueError("Feature input has no rows after applying window and horizon")
    feature_rows.sort(key=lambda row: parse_timestamp(row["target_timestamp"]))
    split_index = max(1, min(len(feature_rows) - 1, int(len(feature_rows) * config.train_fraction)))
    split_boundary = parse_timestamp(feature_rows[split_index]["target_timestamp"])
    for row in feature_rows:
        row["split"] = (
            "train"
            if parse_timestamp(row["target_timestamp"]) < split_boundary
            else "test"
        )
    if not any(row["split"] == "train" for row in feature_rows):
        raise ValueError("Feature split has no training rows")
    if not any(row["split"] == "test" for row in feature_rows):
        raise ValueError("Feature split has no test rows")
    return feature_rows


def write_feature_rows(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    """Write the canonical feature table."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FEATURE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_feature_rows(path: Path) -> list[dict[str, str]]:
    """Read a canonical feature table with strict column ordering."""
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(FEATURE_COLUMNS):
            raise ValueError(
                f"{path}: expected columns {list(FEATURE_COLUMNS)}, got {reader.fieldnames}"
            )
        return [dict(row) for row in reader]
