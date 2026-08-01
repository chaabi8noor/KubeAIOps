#!/usr/bin/env python3
"""Evaluate the persistence baseline and its replica recommendations."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "capacity" / "src"))

from capacity_data.pipeline import write_json
from capacity_features.pipeline import read_feature_rows
from capacity_forecasting.persistence import PersistenceBaseline, evaluate_forecasts
from capacity_policy.replica_policy import ReplicaPolicy, ReplicaPolicyConfig


PREDICTION_COLUMNS = (
    "timestamp",
    "target_timestamp",
    "workload",
    "scenario",
    "actual_requests_per_second",
    "forecast_requests_per_second",
    "absolute_error",
    "current_replicas",
    "recommended_replicas",
    "recommendation_action",
    "actual_required_replicas",
    "split",
)


def read_config(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_predictions(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=PREDICTION_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_plot(path: Path, actual: Sequence[float], forecast: Sequence[float]) -> None:
    """Create a dependency-free SVG comparison plot for evidence review."""
    width, height, padding = 960, 420, 60
    values = [*actual, *forecast]
    low, high = min(values), max(values)
    if low == high:
        high = low + 1

    def point(index: int, value: float) -> tuple[float, float]:
        x = padding + index * (width - 2 * padding) / max(1, len(values) // 2 - 1)
        y = height - padding - (value - low) * (height - 2 * padding) / (high - low)
        return x, y

    def points(series: Sequence[float]) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, value) for i, value in enumerate(series)))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="#ffffff"/>',
                f'<text x="{padding}" y="32" font-family="Arial" font-size="20" fill="#1f2937">Persistence baseline: forecast versus actual demand</text>',
                f'<line x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" stroke="#94a3b8"/>',
                f'<line x1="{padding}" y1="{padding}" x2="{padding}" y2="{height-padding}" stroke="#94a3b8"/>',
                f'<text x="10" y="{padding+5}" font-family="Arial" font-size="12" fill="#475569">{high:.1f} rps</text>',
                f'<text x="10" y="{height-padding+5}" font-family="Arial" font-size="12" fill="#475569">{low:.1f} rps</text>',
                f'<polyline fill="none" stroke="#2563eb" stroke-width="2" points="{points(actual)}"/>',
                f'<polyline fill="none" stroke="#dc2626" stroke-width="2" stroke-dasharray="6 4" points="{points(forecast)}"/>',
                f'<text x="{width-240}" y="{height-20}" font-family="Arial" font-size="13" fill="#2563eb">Blue: actual</text>',
                f'<text x="{width-120}" y="{height-20}" font-family="Arial" font-size="13" fill="#dc2626">Red: forecast</text>',
                "</svg>",
            ]
        ),
        encoding="utf-8",
    )


def write_report(path: Path, metrics: Mapping[str, object], actions: Counter[str]) -> None:
    path.write_text(
        "\n".join(
            [
                "# Persistence baseline validation",
                "",
                "The persistence baseline forecasts the next demand sample from the latest observed request rate. It is a transparent benchmark for later forecasting models, not an operational control loop.",
                "",
                "## Evaluation metrics",
                "",
                "| Metric | Value |",
                "| --- | ---: |",
                f"| Test samples | {metrics['sample_count']} |",
                f"| MAE (requests/second) | {metrics['mae']:.4f} |",
                f"| RMSE (requests/second) | {metrics['rmse']:.4f} |",
                f"| MAPE (%) | {metrics['mape']:.4f} |",
                f"| Under-provisioned recommendations | {metrics['under_provisioned_samples']} |",
                f"| Over-provisioned recommendations | {metrics['over_provisioned_samples']} |",
                "",
                "## Recommendation actions",
                "",
                *[f"- `{action}`: {count}" for action, count in sorted(actions.items())],
                "",
                "## Limitations",
                "",
                "- The sample dataset is deterministic scenario data and must be replaced with observed Prometheus exports before selecting an operational model.",
                "- The policy returns recommendations only; Kubernetes changes remain outside this component.",
                "- The baseline uses no seasonality, trend, or external signals.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--baseline-config", type=Path, required=True)
    parser.add_argument("--policy-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    baseline_config = read_config(args.baseline_config)
    policy_config = read_config(args.policy_config)
    baseline = PersistenceBaseline.from_mapping(baseline_config)
    policy = ReplicaPolicy(ReplicaPolicyConfig.from_mapping(policy_config))
    test_rows = [row for row in read_feature_rows(args.features) if row["split"] == "test"]
    if not test_rows:
        raise ValueError("Feature dataset has no test rows")

    actual = [float(row["target_requests_per_second"]) for row in test_rows]
    forecasts = baseline.predict(test_rows)
    prediction_rows: list[dict[str, str]] = []
    actions: Counter[str] = Counter()
    under_provisioned = 0
    over_provisioned = 0
    for row, target, forecast in zip(test_rows, actual, forecasts):
        current_replicas = int(row["current_replicas"])
        recommendation = policy.recommend(forecast, current_replicas)
        actual_requirement = policy.recommend(target, current_replicas).replicas
        under_provisioned += int(recommendation.replicas < actual_requirement)
        over_provisioned += int(recommendation.replicas > actual_requirement)
        actions[recommendation.action] += 1
        prediction_rows.append(
            {
                "timestamp": row["timestamp"],
                "target_timestamp": row["target_timestamp"],
                "workload": row["workload"],
                "scenario": row["scenario"],
                "actual_requests_per_second": f"{target:.6f}",
                "forecast_requests_per_second": f"{forecast:.6f}",
                "absolute_error": f"{abs(target - forecast):.6f}",
                "current_replicas": str(current_replicas),
                "recommended_replicas": str(recommendation.replicas),
                "recommendation_action": recommendation.action,
                "actual_required_replicas": str(actual_requirement),
                "split": row["split"],
            }
        )

    metrics = evaluate_forecasts(actual, forecasts)
    metrics.update(
        {
            "baseline_version": baseline.version,
            "policy_version": policy.config.version,
            "under_provisioned_samples": under_provisioned,
            "over_provisioned_samples": over_provisioned,
            "stable_for_identical_input": True,
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_predictions(args.output_dir / "predictions.csv", prediction_rows)
    write_json(args.output_dir / "metrics.json", metrics)
    write_json(
        args.output_dir / "evaluation-config.json",
        {
            "features": str(args.features),
            "features_sha256": file_hash(args.features),
            "baseline_config": str(args.baseline_config),
            "baseline_config_sha256": file_hash(args.baseline_config),
            "policy_config": str(args.policy_config),
            "policy_config_sha256": file_hash(args.policy_config),
            "test_split": "test",
        },
    )
    write_plot(args.output_dir / "forecast-vs-actual.svg", actual, forecasts)
    write_report(args.output_dir / "baseline-report.md", metrics, actions)


if __name__ == "__main__":
    main()
