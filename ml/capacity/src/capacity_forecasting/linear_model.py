"""Dependency-free ridge regression for capacity forecasting."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


class PrimaryModelConfigurationError(ValueError):
    """Raised when a primary-model configuration is incomplete or unsafe."""


class PrimaryModelInputError(ValueError):
    """Raised when model input cannot safely produce a forecast."""


@dataclass(frozen=True)
class PrimaryModelConfig:
    version: str
    method: str
    feature_columns: tuple[str, ...]
    regularization: float
    minimum_training_rows: int
    categorical_feature_column: str | None
    fallback_feature_column: str
    maximum_normalized_distance: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "PrimaryModelConfig":
        try:
            feature_columns = tuple(str(item) for item in value["feature_columns"])
            config = cls(
                version=str(value["version"]).strip(),
                method=str(value["method"]).strip(),
                feature_columns=feature_columns,
                regularization=float(value["regularization"]),
                minimum_training_rows=int(value["minimum_training_rows"]),
                categorical_feature_column=(
                    str(value["categorical_feature_column"]).strip()
                    if value.get("categorical_feature_column") is not None
                    else None
                ),
                fallback_feature_column=str(
                    value.get("fallback_feature_column", feature_columns[0])
                ).strip(),
                maximum_normalized_distance=float(
                    value.get("maximum_normalized_distance", 1.0)
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PrimaryModelConfigurationError("Invalid primary-model configuration") from error
        if not config.version:
            raise PrimaryModelConfigurationError("Primary-model configuration requires a version")
        if config.method not in {"ridge_linear_regression", "adaptive_nearest_neighbor"}:
            raise PrimaryModelConfigurationError("Unsupported primary-model method")
        if not config.feature_columns or len(set(config.feature_columns)) != len(config.feature_columns):
            raise PrimaryModelConfigurationError("Feature columns must be non-empty and unique")
        if config.regularization < 0:
            raise PrimaryModelConfigurationError("regularization must be non-negative")
        if config.minimum_training_rows < len(config.feature_columns) + 1:
            raise PrimaryModelConfigurationError(
                "minimum_training_rows must exceed the number of model parameters"
            )
        if config.fallback_feature_column not in config.feature_columns:
            raise PrimaryModelConfigurationError(
                "fallback_feature_column must be included in feature_columns"
            )
        if config.method == "adaptive_nearest_neighbor" and not config.categorical_feature_column:
            raise PrimaryModelConfigurationError(
                "adaptive_nearest_neighbor requires categorical_feature_column"
            )
        if config.maximum_normalized_distance <= 0:
            raise PrimaryModelConfigurationError(
                "maximum_normalized_distance must be positive"
            )
        return config


def _number(row: Mapping[str, object], column: str) -> float:
    try:
        value = float(row[column])
    except (KeyError, TypeError, ValueError) as error:
        raise PrimaryModelInputError(f"Missing numeric feature {column!r}") from error
    if not math.isfinite(value):
        raise PrimaryModelInputError(f"Feature {column!r} must be finite")
    return value


@dataclass(frozen=True)
class FeaturePreprocessor:
    feature_columns: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]

    @classmethod
    def fit(
        cls, rows: Sequence[Mapping[str, object]], feature_columns: Sequence[str]
    ) -> "FeaturePreprocessor":
        columns = tuple(feature_columns)
        if not rows:
            raise PrimaryModelInputError("Cannot fit a preprocessor without training rows")
        values = [[_number(row, column) for row in rows] for column in columns]
        means = tuple(sum(column) / len(column) for column in values)
        scales = tuple(
            max(
                math.sqrt(sum((value - mean) ** 2 for value in column) / len(column)),
                1.0e-12,
            )
            for column, mean in zip(values, means)
        )
        return cls(columns, means, scales)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "FeaturePreprocessor":
        try:
            columns = tuple(str(item) for item in value["feature_columns"])
            means = tuple(float(item) for item in value["means"])
            scales = tuple(float(item) for item in value["scales"])
        except (KeyError, TypeError, ValueError) as error:
            raise PrimaryModelConfigurationError("Invalid preprocessor artifact") from error
        if not columns or len(columns) != len(means) or len(columns) != len(scales):
            raise PrimaryModelConfigurationError("Preprocessor artifact has inconsistent feature metadata")
        if any(not math.isfinite(value) for value in (*means, *scales)) or any(
            value <= 0 for value in scales
        ):
            raise PrimaryModelConfigurationError("Preprocessor artifact has invalid numeric values")
        return cls(columns, means, scales)

    def transform_row(self, row: Mapping[str, object]) -> tuple[float, ...]:
        return tuple(
            (_number(row, column) - mean) / scale
            for column, mean, scale in zip(self.feature_columns, self.means, self.scales)
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "format_version": "capacity-preprocessor/v1",
            "feature_columns": list(self.feature_columns),
            "means": list(self.means),
            "scales": list(self.scales),
        }


def _solve_linear_system(matrix: list[list[float]], target: list[float]) -> list[float]:
    """Solve a square system deterministically with partial pivoting."""
    size = len(matrix)
    augmented = [row[:] + [result] for row, result in zip(matrix, target)]
    for pivot_index in range(size):
        pivot_row = max(
            range(pivot_index, size), key=lambda index: abs(augmented[index][pivot_index])
        )
        if abs(augmented[pivot_row][pivot_index]) <= 1.0e-12:
            raise PrimaryModelInputError("Training matrix is singular")
        augmented[pivot_index], augmented[pivot_row] = (
            augmented[pivot_row],
            augmented[pivot_index],
        )
        pivot = augmented[pivot_index][pivot_index]
        augmented[pivot_index] = [value / pivot for value in augmented[pivot_index]]
        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            augmented[row_index] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row_index], augmented[pivot_index])
            ]
    return [row[-1] for row in augmented]


@dataclass(frozen=True)
class RidgeLinearForecast:
    version: str
    method: str
    preprocessor: FeaturePreprocessor
    intercept: float
    coefficients: tuple[float, ...]
    regularization: float

    @classmethod
    def fit(
        cls,
        rows: Sequence[Mapping[str, object]],
        targets: Sequence[float],
        config: PrimaryModelConfig,
    ) -> "RidgeLinearForecast":
        if len(rows) != len(targets) or len(rows) < config.minimum_training_rows:
            raise PrimaryModelInputError("Training data does not meet the configured minimum")
        if any(not math.isfinite(float(target)) or float(target) < 0 for target in targets):
            raise PrimaryModelInputError("Training targets must be finite and non-negative")
        preprocessor = FeaturePreprocessor.fit(rows, config.feature_columns)
        design = [[1.0, *preprocessor.transform_row(row)] for row in rows]
        dimensions = len(config.feature_columns) + 1
        normal_matrix = [[0.0 for _ in range(dimensions)] for _ in range(dimensions)]
        normal_target = [0.0 for _ in range(dimensions)]
        for row, target in zip(design, targets):
            for left in range(dimensions):
                normal_target[left] += row[left] * target
                for right in range(dimensions):
                    normal_matrix[left][right] += row[left] * row[right]
        for index in range(1, dimensions):
            normal_matrix[index][index] += config.regularization
        parameters = _solve_linear_system(normal_matrix, normal_target)
        return cls(
            version=config.version,
            method=config.method,
            preprocessor=preprocessor,
            intercept=parameters[0],
            coefficients=tuple(parameters[1:]),
            regularization=config.regularization,
        )

    @classmethod
    def from_artifacts(
        cls, model: Mapping[str, object], preprocessor: Mapping[str, object]
    ) -> "RidgeLinearForecast":
        preprocessor_value = FeaturePreprocessor.from_mapping(preprocessor)
        try:
            version = str(model["model_version"]).strip()
            method = str(model["method"]).strip()
            feature_columns = tuple(str(item) for item in model["feature_columns"])
            intercept = float(model["intercept"])
            coefficients = tuple(float(item) for item in model["coefficients"])
            regularization = float(model["regularization"])
        except (KeyError, TypeError, ValueError) as error:
            raise PrimaryModelConfigurationError("Invalid model artifact") from error
        if (
            not version
            or method != "ridge_linear_regression"
            or feature_columns != preprocessor_value.feature_columns
            or len(coefficients) != len(feature_columns)
            or regularization < 0
            or not all(math.isfinite(value) for value in (intercept, *coefficients))
        ):
            raise PrimaryModelConfigurationError("Model artifact failed compatibility validation")
        return cls(
            version=version,
            method=method,
            preprocessor=preprocessor_value,
            intercept=intercept,
            coefficients=coefficients,
            regularization=regularization,
        )

    def predict_row(self, row: Mapping[str, object]) -> float:
        forecast = self.intercept + sum(
            coefficient * value
            for coefficient, value in zip(self.coefficients, self.preprocessor.transform_row(row))
        )
        if not math.isfinite(forecast):
            raise PrimaryModelInputError("Model forecast is not finite")
        return max(0.0, forecast)

    def predict(self, rows: Sequence[Mapping[str, object]]) -> list[float]:
        return [self.predict_row(row) for row in rows]

    def to_model_mapping(self) -> dict[str, object]:
        return {
            "format_version": "capacity-model/v1",
            "model_name": "capacity-primary",
            "model_version": self.version,
            "method": self.method,
            "feature_columns": list(self.preprocessor.feature_columns),
            "intercept": self.intercept,
            "coefficients": list(self.coefficients),
            "regularization": self.regularization,
        }


@dataclass(frozen=True)
class NearestNeighborReference:
    category: str
    transformed_features: tuple[float, ...]
    target: float


@dataclass(frozen=True)
class AdaptiveNearestNeighborForecast:
    """Forecast from similar observed feature states with a safe persistence fallback."""

    version: str
    preprocessor: FeaturePreprocessor
    categorical_feature_column: str
    fallback_feature_column: str
    maximum_normalized_distance: float
    references: tuple[NearestNeighborReference, ...]

    @classmethod
    def fit(
        cls,
        rows: Sequence[Mapping[str, object]],
        targets: Sequence[float],
        config: PrimaryModelConfig,
    ) -> "AdaptiveNearestNeighborForecast":
        if config.method != "adaptive_nearest_neighbor":
            raise PrimaryModelConfigurationError(
                "Adaptive nearest-neighbor training requires its configured method"
            )
        if len(rows) != len(targets) or len(rows) < config.minimum_training_rows:
            raise PrimaryModelInputError("Training data does not meet the configured minimum")
        preprocessor = FeaturePreprocessor.fit(rows, config.feature_columns)
        references: list[NearestNeighborReference] = []
        for row, target in zip(rows, targets):
            if not math.isfinite(float(target)) or float(target) < 0:
                raise PrimaryModelInputError("Training targets must be finite and non-negative")
            category = str(row.get(config.categorical_feature_column or "", "")).strip()
            if not category:
                raise PrimaryModelInputError("Training rows require a categorical feature value")
            references.append(
                NearestNeighborReference(
                    category=category,
                    transformed_features=preprocessor.transform_row(row),
                    target=float(target),
                )
            )
        return cls(
            version=config.version,
            preprocessor=preprocessor,
            categorical_feature_column=config.categorical_feature_column or "",
            fallback_feature_column=config.fallback_feature_column,
            maximum_normalized_distance=config.maximum_normalized_distance,
            references=tuple(references),
        )

    @classmethod
    def from_artifacts(
        cls, model: Mapping[str, object], preprocessor: Mapping[str, object]
    ) -> "AdaptiveNearestNeighborForecast":
        preprocessor_value = FeaturePreprocessor.from_mapping(preprocessor)
        try:
            version = str(model["model_version"]).strip()
            method = str(model["method"]).strip()
            columns = tuple(str(item) for item in model["feature_columns"])
            category_column = str(model["categorical_feature_column"]).strip()
            fallback_column = str(model["fallback_feature_column"]).strip()
            maximum_distance = float(model["maximum_normalized_distance"])
            references = tuple(
                NearestNeighborReference(
                    category=str(item["category"]).strip(),
                    transformed_features=tuple(
                        float(value) for value in item["transformed_features"]
                    ),
                    target=float(item["target"]),
                )
                for item in model["references"]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise PrimaryModelConfigurationError("Invalid nearest-neighbor model artifact") from error
        if (
            not version
            or method != "adaptive_nearest_neighbor"
            or columns != preprocessor_value.feature_columns
            or not category_column
            or fallback_column not in columns
            or maximum_distance <= 0
            or not references
        ):
            raise PrimaryModelConfigurationError("Model artifact failed compatibility validation")
        for reference in references:
            if (
                not reference.category
                or len(reference.transformed_features) != len(columns)
                or not math.isfinite(reference.target)
                or reference.target < 0
                or not all(math.isfinite(value) for value in reference.transformed_features)
            ):
                raise PrimaryModelConfigurationError("Model artifact has invalid reference values")
        return cls(
            version=version,
            preprocessor=preprocessor_value,
            categorical_feature_column=category_column,
            fallback_feature_column=fallback_column,
            maximum_normalized_distance=maximum_distance,
            references=references,
        )

    def predict_row(self, row: Mapping[str, object]) -> float:
        fallback = _number(row, self.fallback_feature_column)
        if fallback < 0:
            raise PrimaryModelInputError("Fallback demand must be non-negative")
        category = str(row.get(self.categorical_feature_column, "")).strip()
        if not category:
            raise PrimaryModelInputError("Prediction requires a categorical feature value")
        candidates = [reference for reference in self.references if reference.category == category]
        if not candidates:
            raise PrimaryModelInputError("Prediction category is not represented in the frozen model")
        transformed = self.preprocessor.transform_row(row)
        nearest = min(
            candidates,
            key=lambda reference: sum(
                (value - reference_value) ** 2
                for value, reference_value in zip(
                    transformed, reference.transformed_features
                )
            ),
        )
        distance = math.sqrt(
            sum(
                (value - reference_value) ** 2
                for value, reference_value in zip(transformed, nearest.transformed_features)
            )
        )
        return (
            nearest.target
            if distance <= self.maximum_normalized_distance
            else fallback
        )

    def predict(self, rows: Sequence[Mapping[str, object]]) -> list[float]:
        return [self.predict_row(row) for row in rows]

    def to_model_mapping(self) -> dict[str, object]:
        return {
            "format_version": "capacity-model/v1",
            "model_name": "capacity-primary",
            "model_version": self.version,
            "method": "adaptive_nearest_neighbor",
            "feature_columns": list(self.preprocessor.feature_columns),
            "categorical_feature_column": self.categorical_feature_column,
            "fallback_feature_column": self.fallback_feature_column,
            "maximum_normalized_distance": self.maximum_normalized_distance,
            "references": [
                {
                    "category": reference.category,
                    "transformed_features": list(reference.transformed_features),
                    "target": reference.target,
                }
                for reference in self.references
            ],
        }
