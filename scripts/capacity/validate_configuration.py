#!/usr/bin/env python3
"""Validate versioned capacity configuration before packaging or deployment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a YAML mapping")
    return value


def main() -> None:
    pipeline = read_yaml(PROJECT_ROOT / ".gitlab-ci.yml")
    required_jobs = {
        "python-validation",
        "capacity-tests",
        "helm-validation",
        "gitops-validation",
        "capacity-image",
        "capacity-image-scan",
        "capacity-container-smoke",
        "load-test-contract",
    }
    missing_jobs = sorted(required_jobs - set(pipeline))
    if missing_jobs:
        raise ValueError(f"GitLab pipeline is missing jobs: {', '.join(missing_jobs)}")

    model_config = read_yaml(PROJECT_ROOT / "ml" / "capacity" / "config" / "model.yaml")
    if model_config.get("method") != "adaptive_nearest_neighbor":
        raise ValueError("Primary model must use the configured adaptive method")
    if not model_config.get("feature_columns"):
        raise ValueError("Primary model requires a fixed feature list")

    values = read_yaml(PROJECT_ROOT / "helm" / "capacity-api" / "values.yaml")
    if values.get("config", {}).get("modelPath") != "/app/models":
        raise ValueError("Helm values must mount the packaged model path")
    if not values.get("availability", {}).get("podDisruptionBudget", {}).get("enabled"):
        raise ValueError("Helm values must enable the Capacity API PodDisruptionBudget")

    application = read_yaml(PROJECT_ROOT / "gitops" / "applications" / "capacity-api.yaml")
    if application.get("kind") != "Application":
        raise ValueError("GitOps application manifest has an unexpected kind")
    if application.get("spec", {}).get("source", {}).get("repoURL") != (
        "https://gitlab.com/kubeaiops/kubeaiops-platform.git"
    ):
        raise ValueError("GitOps application must reference the GitLab repository")
    policy = application.get("spec", {}).get("syncPolicy", {}).get("automated", {})
    if not policy.get("prune") or not policy.get("selfHeal"):
        raise ValueError("GitOps application must enable pruning and self-healing")

    dashboard = json.loads(
        (PROJECT_ROOT / "monitoring" / "capacity" / "grafana" / "capacity-overview.json").read_text(
            encoding="utf-8"
        )
    )
    if len(dashboard.get("panels", [])) < 10:
        raise ValueError("Capacity dashboard must retain its operational panel set")
    print("Capacity configuration validation passed.")


if __name__ == "__main__":
    main()
