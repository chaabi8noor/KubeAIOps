from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ml" / "capacity" / "src"))

from capacity_forecasting.persistence import PersistenceBaseline, evaluate_forecasts


def baseline() -> PersistenceBaseline:
    return PersistenceBaseline.from_mapping(
        {
            "version": "persistence-test",
            "method": "persistence",
            "feature_column": "current_requests_per_second",
        }
    )


def test_persistence_baseline_returns_the_latest_observed_demand() -> None:
    rows = [
        {"current_requests_per_second": "12.5"},
        {"current_requests_per_second": "40"},
    ]

    assert baseline().predict(rows) == [12.5, 40.0]


def test_evaluation_metrics_are_repeatable() -> None:
    metrics = evaluate_forecasts([10.0, 20.0], [12.0, 18.0])

    assert metrics == {"sample_count": 2, "mae": 2.0, "rmse": 2.0, "mape": 15.0}


def test_baseline_rejects_invalid_demand() -> None:
    with pytest.raises(ValueError, match="finite non-negative"):
        baseline().predict([{"current_requests_per_second": "-1"}])
