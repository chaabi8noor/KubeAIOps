from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ml" / "capacity" / "src"))

from capacity_forecasting import (
    AdaptiveNearestNeighborForecast,
    PrimaryModelConfig,
    PrimaryModelInputError,
    RidgeLinearForecast,
)


def model_config() -> PrimaryModelConfig:
    return PrimaryModelConfig.from_mapping(
        {
            "version": "capacity-primary-test",
            "method": "ridge_linear_regression",
            "feature_columns": ["current_requests_per_second", "request_rate_lag_1"],
            "regularization": 0.000001,
            "minimum_training_rows": 4,
        }
    )


def rows() -> list[dict[str, str]]:
    return [
        {
            "current_requests_per_second": str(value),
            "request_rate_lag_1": str(value - 1),
        }
        for value in range(1, 8)
    ]


def test_primary_model_trains_and_loads_without_the_training_environment() -> None:
    training_rows = rows()
    targets = [float(value * 2 + 3) for value in range(1, 8)]
    trained = RidgeLinearForecast.fit(training_rows, targets, model_config())
    loaded = RidgeLinearForecast.from_artifacts(
        trained.to_model_mapping(), trained.preprocessor.to_mapping()
    )

    assert loaded.predict_row(
        {"current_requests_per_second": "8", "request_rate_lag_1": "7"}
    ) == pytest.approx(19.0, abs=0.001)
    assert loaded.predict(training_rows) == trained.predict(training_rows)


def test_primary_model_rejects_invalid_feature_values() -> None:
    trained = RidgeLinearForecast.fit(rows(), [float(value) for value in range(1, 8)], model_config())

    with pytest.raises(PrimaryModelInputError, match="finite"):
        trained.predict_row(
            {
                "current_requests_per_second": "nan",
                "request_rate_lag_1": "1",
            }
        )


def test_adaptive_nearest_neighbor_uses_a_safe_persistence_fallback() -> None:
    config = PrimaryModelConfig.from_mapping(
        {
            "version": "capacity-neighbor-test",
            "method": "adaptive_nearest_neighbor",
            "feature_columns": ["current_requests_per_second", "request_rate_lag_1"],
            "regularization": 0.0,
            "minimum_training_rows": 4,
            "categorical_feature_column": "scenario",
            "fallback_feature_column": "current_requests_per_second",
            "maximum_normalized_distance": 0.2,
        }
    )
    training_rows = [
        {**row, "scenario": "normal"}
        for row in rows()
    ]
    trained = AdaptiveNearestNeighborForecast.fit(
        training_rows, [float(value * 2) for value in range(1, 8)], config
    )
    loaded = AdaptiveNearestNeighborForecast.from_artifacts(
        trained.to_model_mapping(), trained.preprocessor.to_mapping()
    )

    assert loaded.predict_row({**training_rows[2], "current_requests_per_second": "3"}) == 6.0
    assert loaded.predict_row(
        {
            "current_requests_per_second": "100",
            "request_rate_lag_1": "99",
            "scenario": "normal",
        }
    ) == 100.0
