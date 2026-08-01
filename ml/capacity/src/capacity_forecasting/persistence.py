"""A transparent persistence baseline kept separate from future ML models."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


class BaselineConfigurationError(ValueError):
    """Raised when baseline configuration does not describe persistence."""


@dataclass(frozen=True)
class PersistenceBaseline:
    version: str
    feature_column: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "PersistenceBaseline":
        if value.get("method") != "persistence":
            raise BaselineConfigurationError("Only the persistence baseline is supported")
        version = str(value.get("version", "")).strip()
        feature_column = str(value.get("feature_column", "")).strip()
        if not version or not feature_column:
            raise BaselineConfigurationError("Baseline configuration requires version and feature_column")
        return cls(version=version, feature_column=feature_column)

    def predict(self, rows: Sequence[Mapping[str, str]]) -> list[float]:
        """Forecast the next demand value as the latest observed demand value."""
        predictions: list[float] = []
        for row in rows:
            try:
                value = float(row[self.feature_column])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(
                    f"Baseline input is missing numeric {self.feature_column!r}"
                ) from error
            if not math.isfinite(value) or value < 0:
                raise ValueError("Baseline input must be a finite non-negative value")
            predictions.append(value)
        return predictions


def evaluate_forecasts(actual: Sequence[float], predicted: Sequence[float]) -> dict[str, float | int]:
    """Calculate deterministic error metrics for a forecast series."""
    if len(actual) != len(predicted) or not actual:
        raise ValueError("actual and predicted forecasts must be non-empty and aligned")
    errors = [prediction - target for target, prediction in zip(actual, predicted)]
    absolute_errors = [abs(error) for error in errors]
    squared_errors = [error * error for error in errors]
    nonzero_targets = [
        abs(error) / target
        for target, error in zip(actual, errors)
        if target != 0
    ]
    mae = sum(absolute_errors) / len(absolute_errors)
    rmse = math.sqrt(sum(squared_errors) / len(squared_errors))
    mape = (
        sum(nonzero_targets) / len(nonzero_targets) * 100
        if nonzero_targets
        else 0.0
    )
    return {
        "sample_count": len(actual),
        "mae": round(mae, 10),
        "rmse": round(rmse, 10),
        "mape": round(mape, 10),
    }
