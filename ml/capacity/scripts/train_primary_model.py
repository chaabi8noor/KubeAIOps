#!/usr/bin/env python3
"""Train, evaluate, and freeze the primary capacity forecasting model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "capacity" / "src"))

from capacity_data.pipeline import write_json
from capacity_features.pipeline import read_feature_rows
from capacity_forecasting import (
    AdaptiveNearestNeighborForecast,
    PrimaryModelConfig,
    RidgeLinearForecast,
    evaluate_forecasts,
)
from capacity_policy.replica_policy import ReplicaPolicy, ReplicaPolicyConfig


PREDICTION_COLUMNS = (
    "timestamp",
    "target_timestamp",
    "workload",
    "scenario",
    "actual_requests_per_second",
    "baseline_forecast_requests_per_second",
    "primary_forecast_requests_per_second",
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


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_predictions(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=PREDICTION_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def policy_statistics(
    rows: Sequence[Mapping[str, str]], forecasts: Sequence[float], policy: ReplicaPolicy
) -> tuple[dict[str, int], Counter[str], list[dict[str, str]]]:
    under_provisioned = 0
    over_provisioned = 0
    actions: Counter[str] = Counter()
    outputs: list[dict[str, str]] = []
    for row, forecast in zip(rows, forecasts):
        actual = float(row["target_requests_per_second"])
        current_replicas = int(row["current_replicas"])
        recommendation = policy.recommend(forecast, current_replicas)
        actual_requirement = policy.recommend(actual, current_replicas).replicas
        under_provisioned += int(recommendation.replicas < actual_requirement)
        over_provisioned += int(recommendation.replicas > actual_requirement)
        actions[recommendation.action] += 1
        outputs.append(
            {
                "timestamp": row["timestamp"],
                "target_timestamp": row["target_timestamp"],
                "workload": row["workload"],
                "scenario": row["scenario"],
                "actual_requests_per_second": f"{actual:.6f}",
                "baseline_forecast_requests_per_second": row[
                    "current_requests_per_second"
                ],
                "primary_forecast_requests_per_second": f"{forecast:.6f}",
                "absolute_error": f"{abs(actual - forecast):.6f}",
                "current_replicas": str(current_replicas),
                "recommended_replicas": str(recommendation.replicas),
                "recommendation_action": recommendation.action,
                "actual_required_replicas": str(actual_requirement),
                "split": row["split"],
            }
        )
    return (
        {
            "under_provisioned_samples": under_provisioned,
            "over_provisioned_samples": over_provisioned,
        },
        actions,
        outputs,
    )


def scenario_metrics(rows: Sequence[Mapping[str, str]], forecasts: Sequence[float]) -> dict[str, dict[str, float | int]]:
    groups: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for row, forecast in zip(rows, forecasts):
        groups[row["scenario"]].append((float(row["target_requests_per_second"]), forecast))
    return {
        scenario: evaluate_forecasts(
            [actual for actual, _ in values], [forecast for _, forecast in values]
        )
        for scenario, values in sorted(groups.items())
    }


def write_comparison_report(
    path: Path,
    baseline_metrics: Mapping[str, object],
    primary_metrics: Mapping[str, object],
    per_scenario: Mapping[str, Mapping[str, float | int]],
    actions: Counter[str],
    selected: bool,
    model_version: str,
) -> None:
    decision = (
        f"`{model_version}` is selected for API integration because its MAE is lower than the persistence baseline."
        if selected
        else f"`{model_version}` is not selected for API integration because it did not improve on the persistence baseline."
    )
    lines = [
        "# Primary model comparison",
        "",
        decision,
        "",
        "## Forecast accuracy",
        "",
        "| Metric | Persistence baseline | Primary model |",
        "| --- | ---: | ---: |",
        f"| MAE (requests/second) | {float(baseline_metrics['mae']):.4f} | {float(primary_metrics['mae']):.4f} |",
        f"| RMSE (requests/second) | {float(baseline_metrics['rmse']):.4f} | {float(primary_metrics['rmse']):.4f} |",
        f"| MAPE (%) | {float(baseline_metrics['mape']):.4f} | {float(primary_metrics['mape']):.4f} |",
        f"| Under-provisioned samples | {int(baseline_metrics['under_provisioned_samples'])} | {int(primary_metrics['under_provisioned_samples'])} |",
        f"| Over-provisioned samples | {int(baseline_metrics['over_provisioned_samples'])} | {int(primary_metrics['over_provisioned_samples'])} |",
        "",
        "## Scenario stability",
        "",
        "| Scenario | Samples | MAE | RMSE | MAPE (%) |",
        "| --- | ---: | ---: | ---: | ---: |",
        *[
            f"| {scenario} | {values['sample_count']} | {float(values['mae']):.4f} | {float(values['rmse']):.4f} | {float(values['mape']):.4f} |"
            for scenario, values in sorted(per_scenario.items())
        ],
        "",
        "## Recommendation stability",
        "",
        "| Action | Samples |",
        "| --- | ---: |",
        *[f"| {action} | {count} |" for action, count in sorted(actions.items())],
        "",
        "Repeated predictions and recommendations returned identical values for the same evaluation input.",
        "",
        "## Limitations and operational interpretation",
        "",
        "- This model was trained on deterministic scenario data; observed Prometheus exports are required before any production threshold change.",
        "- The result is an explainable forecast and bounded recommendation, not a direct Kubernetes scaling command.",
        "- Prediction failures are handled by the API without changing Kubernetes state.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_model_card(
    path: Path,
    config: PrimaryModelConfig,
    primary_metrics: Mapping[str, object],
    dataset_version: str,
) -> None:
    path.write_text(
        "\n".join(
            [
                "# Capacity primary model card",
                "",
                f"## Model identity\n\n- Version: `{config.version}`\n- Method: `{config.method}`",
                "",
                "## Intended use",
                "",
                "Forecast the configured short horizon of workload requests per second and provide evidence to the separate replica recommendation policy.",
                "",
                "## Inputs and outputs",
                "",
                f"- Inputs: {', '.join(f'`{column}`' for column in config.feature_columns)}",
                "- Output: finite, non-negative forecast requests per second.",
                "- Operational result: a bounded recommendation from the independent replica policy.",
                "",
                "## Training and evaluation",
                "",
                f"- Dataset: `{dataset_version}`",
                "- Split: feature rows are separated by target timestamp before model training.",
                f"- Test MAE: {float(primary_metrics['mae']):.4f} requests/second",
                f"- Test RMSE: {float(primary_metrics['rmse']):.4f} requests/second",
                f"- Test MAPE: {float(primary_metrics['mape']):.4f}%",
                "",
                "## Limitations and failure conditions",
                "",
                "- Deterministic scenario data does not replace observed production traffic.",
                "- Missing, non-numeric, or non-finite inputs must fail the prediction path safely.",
                "- The model is not an authority to mutate Kubernetes resources.",
                "",
                "## Versioning process",
                "",
                "A frozen release includes model, preprocessor, feature order, configuration, dataset identity, evaluation report, and source commit. Any input or configuration change requires a new model version and comparison run.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--model-config", type=Path, required=True)
    parser.add_argument("--policy-config", type=Path, required=True)
    parser.add_argument("--baseline-metrics", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()

    model_config_mapping = read_config(args.model_config)
    config = PrimaryModelConfig.from_mapping(model_config_mapping)
    policy = ReplicaPolicy(ReplicaPolicyConfig.from_mapping(read_config(args.policy_config)))
    baseline_metrics = read_json(args.baseline_metrics)
    rows = read_feature_rows(args.features)
    training_rows = [row for row in rows if row["split"] == "train"]
    test_rows = [row for row in rows if row["split"] == "test"]
    if not test_rows:
        raise ValueError("Feature dataset has no test rows")
    targets = [float(row["target_requests_per_second"]) for row in training_rows]
    model = (
        RidgeLinearForecast.fit(training_rows, targets, config)
        if config.method == "ridge_linear_regression"
        else AdaptiveNearestNeighborForecast.fit(training_rows, targets, config)
    )
    forecasts = model.predict(test_rows)
    repeated_forecasts = model.predict(test_rows)
    if forecasts != repeated_forecasts:
        raise RuntimeError("Primary-model predictions are not stable for identical input")
    actual = [float(row["target_requests_per_second"]) for row in test_rows]
    metrics = evaluate_forecasts(actual, forecasts)
    policy_metrics, actions, prediction_rows = policy_statistics(test_rows, forecasts, policy)
    metrics.update(
        {
            "model_version": config.version,
            "policy_version": policy.config.version,
            "stable_for_identical_input": True,
            **policy_metrics,
        }
    )
    selected = float(metrics["mae"]) < float(baseline_metrics["mae"])
    metrics["selected_for_api"] = selected
    metrics["baseline_mae"] = float(baseline_metrics["mae"])
    metrics["mae_improvement"] = round(
        float(baseline_metrics["mae"]) - float(metrics["mae"]), 10
    )

    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    args.evaluation_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.artifact_dir / "model.json", model.to_model_mapping())
    write_json(args.artifact_dir / "preprocessor.json", model.preprocessor.to_mapping())
    write_json(args.artifact_dir / "training-config.json", model_config_mapping)
    write_json(
        args.artifact_dir / "model-version.json",
        {
            "model_version": config.version,
            "dataset_version": args.dataset_version,
            "feature_order": list(config.feature_columns),
            "source_commit": args.source_commit,
            "frozen": True,
        },
    )
    write_json(
        args.artifact_dir / "training-metadata.json",
        {
            "dataset_version": args.dataset_version,
            "feature_dataset": str(args.features),
            "feature_dataset_sha256": file_hash(args.features),
            "model_config": str(args.model_config),
            "model_config_sha256": file_hash(args.model_config),
            "policy_config": str(args.policy_config),
            "policy_config_sha256": file_hash(args.policy_config),
            "baseline_metrics": str(args.baseline_metrics),
            "baseline_metrics_sha256": file_hash(args.baseline_metrics),
            "source_commit": args.source_commit,
            "training_rows": len(training_rows),
            "test_rows": len(test_rows),
        },
    )
    write_json(args.evaluation_dir / "metrics.json", metrics)
    write_json(
        args.evaluation_dir / "evaluation-config.json",
        {
            "model_artifact": str(args.artifact_dir / "model.json"),
            "model_artifact_sha256": file_hash(args.artifact_dir / "model.json"),
            "preprocessor_artifact": str(args.artifact_dir / "preprocessor.json"),
            "preprocessor_artifact_sha256": file_hash(args.artifact_dir / "preprocessor.json"),
            "test_split": "test",
            "model_selected_for_api": selected,
        },
    )
    write_predictions(args.evaluation_dir / "predictions.csv", prediction_rows)
    write_comparison_report(
        args.evaluation_dir / "comparison-report.md",
        baseline_metrics,
        metrics,
        scenario_metrics(test_rows, forecasts),
        actions,
        selected,
        config.version,
    )
    write_model_card(
        args.artifact_dir / "model-card.md", config, metrics, args.dataset_version
    )
    if not selected:
        raise RuntimeError("Primary model did not beat the persistence baseline")


if __name__ == "__main__":
    main()
