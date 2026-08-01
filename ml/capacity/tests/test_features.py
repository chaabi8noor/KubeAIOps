from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ml" / "capacity" / "src"))

from capacity_features.pipeline import FeatureConfig, build_feature_rows


def observation(index: int) -> dict[str, str]:
    return {
        "timestamp": f"2026-08-01T09:0{index}:00Z",
        "workload": "demo-workload",
        "scenario": "normal",
        "requests_per_second": str(10 + index * 10),
        "cpu_utilization_ratio": "0.5",
        "memory_working_set_bytes": "200000000",
        "p95_latency_seconds": "0.05",
        "error_ratio": "0.001",
        "replicas": "2",
        "scaling_event": "none",
    }


def config() -> FeatureConfig:
    return FeatureConfig.from_mapping(
        {
            "version": "features-test",
            "horizon_steps": 1,
            "rolling_window_steps": 3,
            "train_fraction": 0.5,
        }
    )


def test_feature_pipeline_uses_only_current_and_past_observations() -> None:
    rows = build_feature_rows([observation(index) for index in range(6)], config())

    assert len(rows) == 3
    assert rows[0]["current_requests_per_second"] == "30"
    assert rows[0]["request_rate_lag_1"] == "20"
    assert rows[0]["request_rate_rolling_mean"] == "20"
    assert rows[0]["target_requests_per_second"] == "40"
    assert rows[0]["target_timestamp"] > rows[0]["timestamp"]


def test_feature_pipeline_splits_on_target_timestamp() -> None:
    rows = build_feature_rows([observation(index) for index in range(8)], config())
    training_targets = [row["target_timestamp"] for row in rows if row["split"] == "train"]
    test_targets = [row["target_timestamp"] for row in rows if row["split"] == "test"]

    assert training_targets
    assert test_targets
    assert max(training_targets) < min(test_targets)
