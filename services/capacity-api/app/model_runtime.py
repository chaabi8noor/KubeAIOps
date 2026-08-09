"""Load and run the frozen capacity forecast without training dependencies."""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import yaml


class ModelArtifactError(RuntimeError):
    """Raised when a frozen model package is absent, changed, or incompatible."""


class FeatureSourceError(RuntimeError):
    """Raised when the configured runtime feature source is unavailable."""


class FeatureValidationError(ValueError):
    """Raised when runtime feature values are unsafe for prediction."""


class PolicyConfigurationError(ValueError):
    """Raised when the packaged replica policy is invalid."""


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelArtifactError(f"Cannot read model artifact {path.name}") from error
    if not isinstance(value, dict):
        raise ModelArtifactError(f"Model artifact {path.name} must contain an object")
    return value


def _number(name: str, value: object, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise FeatureValidationError(f"{name} must be numeric") from error
    if not math.isfinite(number):
        raise FeatureValidationError(f"{name} must be finite")
    if minimum is not None and number < minimum:
        raise FeatureValidationError(f"{name} must be at least {minimum}")
    if maximum is not None and number > maximum:
        raise FeatureValidationError(f"{name} must be at most {maximum}")
    return number


def _env_number(name: str, default: str, *, minimum: float | None = None, maximum: float | None = None) -> float:
    return _number(name, os.getenv(name, default), minimum=minimum, maximum=maximum)


def resolve_model_directory(path: Path) -> Path:
    """Accept either a model directory or a root containing exactly one model."""
    if (path / "model.json").is_file():
        return path
    if not path.is_dir():
        raise ModelArtifactError(f"Model path does not exist: {path}")
    candidates = sorted(
        child for child in path.iterdir() if child.is_dir() and (child / "model.json").is_file()
    )
    if len(candidates) != 1:
        raise ModelArtifactError("Model path must contain exactly one frozen model directory")
    return candidates[0]


@dataclass(frozen=True)
class RuntimeInput:
    current_requests_per_second: float
    request_rate_lag_1: float
    request_rate_rolling_mean: float
    cpu_utilization_ratio: float
    p95_latency_seconds: float
    error_ratio: float
    current_replicas: int
    scenario: str

    @classmethod
    def from_environment(cls) -> "RuntimeInput":
        if os.getenv("CAPACITY_METRICS_MODE", "configured") != "configured":
            raise FeatureSourceError("Configured runtime metrics source is unavailable")
        replicas = _env_number("CAPACITY_CURRENT_REPLICAS", "2", minimum=1)
        if not replicas.is_integer():
            raise FeatureValidationError("CAPACITY_CURRENT_REPLICAS must be an integer")
        scenario = os.getenv("CAPACITY_SCENARIO", "normal").strip()
        if not scenario:
            raise FeatureValidationError("CAPACITY_SCENARIO is required")
        return cls(
            current_requests_per_second=_env_number(
                "CAPACITY_CURRENT_REQUESTS_PER_SECOND", "12.124", minimum=0
            ),
            request_rate_lag_1=_env_number(
                "CAPACITY_REQUEST_RATE_LAG_1", "12.065", minimum=0
            ),
            request_rate_rolling_mean=_env_number(
                "CAPACITY_REQUEST_RATE_ROLLING_MEAN", "12.063", minimum=0
            ),
            cpu_utilization_ratio=_env_number(
                "CAPACITY_CPU_UTILIZATION", "0.362", minimum=0, maximum=1
            ),
            p95_latency_seconds=_env_number(
                "CAPACITY_P95_LATENCY_SECONDS", "0.048", minimum=0
            ),
            error_ratio=_env_number("CAPACITY_ERROR_RATIO", "0.001", minimum=0, maximum=1),
            current_replicas=int(replicas),
            scenario=scenario,
        )

    def feature_mapping(self) -> dict[str, object]:
        return {
            "current_requests_per_second": self.current_requests_per_second,
            "request_rate_lag_1": self.request_rate_lag_1,
            "request_rate_rolling_mean": self.request_rate_rolling_mean,
            "cpu_utilization_ratio": self.cpu_utilization_ratio,
            "p95_latency_seconds": self.p95_latency_seconds,
            "error_ratio": self.error_ratio,
            "current_replicas": self.current_replicas,
            "scenario": self.scenario,
        }


@dataclass(frozen=True)
class ReplicaPolicy:
    version: str
    minimum_replicas: int
    maximum_replicas: int
    requests_per_second_per_replica: float
    target_utilization: float
    downscale_tolerance: float

    @classmethod
    def from_path(cls, path: Path) -> "ReplicaPolicy":
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            policy = cls(
                version=str(value["version"]).strip(),
                minimum_replicas=int(value["minimum_replicas"]),
                maximum_replicas=int(value["maximum_replicas"]),
                requests_per_second_per_replica=float(value["requests_per_second_per_replica"]),
                target_utilization=float(value["target_utilization"]),
                downscale_tolerance=float(value["downscale_tolerance"]),
            )
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as error:
            raise PolicyConfigurationError("Replica-policy artifact is invalid") from error
        if (
            not policy.version
            or policy.minimum_replicas < 1
            or policy.maximum_replicas < policy.minimum_replicas
            or policy.requests_per_second_per_replica <= 0
            or not 0 < policy.target_utilization <= 1
            or not 0 <= policy.downscale_tolerance < 1
        ):
            raise PolicyConfigurationError("Replica-policy artifact has invalid values")
        return policy

    @property
    def effective_capacity_per_replica(self) -> float:
        return self.requests_per_second_per_replica * self.target_utilization

    def recommend(self, forecast: float, current_replicas: int) -> tuple[int, str, str]:
        current = min(self.maximum_replicas, max(self.minimum_replicas, current_replicas))
        required = math.ceil(forecast / self.effective_capacity_per_replica)
        desired = min(self.maximum_replicas, max(self.minimum_replicas, required))
        if desired > current:
            return (
                desired,
                "scale_up",
                "Predicted demand exceeds the safe capacity of current replicas.",
            )
        downscale_threshold = (
            current * self.effective_capacity_per_replica * (1 - self.downscale_tolerance)
        )
        if desired < current and forecast <= downscale_threshold:
            return (
                desired,
                "scale_down",
                "Predicted demand remains below the guarded downscale threshold.",
            )
        return current, "hold", "Predicted demand is within the guarded capacity range."


@dataclass(frozen=True)
class ModelReference:
    category: str
    transformed_features: tuple[float, ...]
    target: float


@dataclass(frozen=True)
class CapacityModelRuntime:
    model_version: str
    feature_columns: tuple[str, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    categorical_feature_column: str
    fallback_feature_column: str
    maximum_normalized_distance: float
    references: tuple[ModelReference, ...]
    policy: ReplicaPolicy

    @classmethod
    def from_directory(cls, directory: Path) -> "CapacityModelRuntime":
        required = (
            "manifest.json",
            "model.json",
            "preprocessor.json",
            "model-version.json",
            "replica-policy.yaml",
        )
        missing = [name for name in required if not (directory / name).is_file()]
        if missing:
            raise ModelArtifactError(f"Model package is missing: {', '.join(missing)}")
        manifest = _read_json(directory / "manifest.json")
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ModelArtifactError("Model package manifest has no file hashes")
        for name, expected_hash in files.items():
            path = directory / str(name)
            if not path.is_file() or _file_hash(path) != expected_hash:
                raise ModelArtifactError(f"Model package hash validation failed for {name}")

        model = _read_json(directory / "model.json")
        preprocessor = _read_json(directory / "preprocessor.json")
        version_record = _read_json(directory / "model-version.json")
        try:
            version = str(model["model_version"]).strip()
            method = str(model["method"]).strip()
            columns = tuple(str(value) for value in model["feature_columns"])
            preprocessor_columns = tuple(str(value) for value in preprocessor["feature_columns"])
            means = tuple(float(value) for value in preprocessor["means"])
            scales = tuple(float(value) for value in preprocessor["scales"])
            category_column = str(model["categorical_feature_column"]).strip()
            fallback_column = str(model["fallback_feature_column"]).strip()
            maximum_distance = float(model["maximum_normalized_distance"])
            references = tuple(
                ModelReference(
                    category=str(item["category"]).strip(),
                    transformed_features=tuple(
                        float(value) for value in item["transformed_features"]
                    ),
                    target=float(item["target"]),
                )
                for item in model["references"]
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ModelArtifactError("Model package has incompatible artifacts") from error
        if (
            method != "adaptive_nearest_neighbor"
            or not version
            or version != str(version_record.get("model_version", "")).strip()
            or version != str(manifest.get("model_version", "")).strip()
            or not version_record.get("frozen")
            or columns != preprocessor_columns
            or len(columns) != len(means)
            or len(columns) != len(scales)
            or fallback_column not in columns
            or not category_column
            or maximum_distance <= 0
            or not references
            or any(scale <= 0 or not math.isfinite(scale) for scale in scales)
            or any(not math.isfinite(mean) for mean in means)
        ):
            raise ModelArtifactError("Model package failed startup compatibility validation")
        for reference in references:
            if (
                not reference.category
                or len(reference.transformed_features) != len(columns)
                or not math.isfinite(reference.target)
                or reference.target < 0
                or not all(math.isfinite(value) for value in reference.transformed_features)
            ):
                raise ModelArtifactError("Model package contains invalid reference data")
        return cls(
            model_version=version,
            feature_columns=columns,
            means=means,
            scales=scales,
            categorical_feature_column=category_column,
            fallback_feature_column=fallback_column,
            maximum_normalized_distance=maximum_distance,
            references=references,
            policy=ReplicaPolicy.from_path(directory / "replica-policy.yaml"),
        )

    def predict(self, feature_input: RuntimeInput) -> float:
        values = feature_input.feature_mapping()
        transformed: list[float] = []
        for column, mean, scale in zip(self.feature_columns, self.means, self.scales):
            value = _number(column, values.get(column), minimum=0)
            transformed.append((value - mean) / scale)
        category = str(values.get(self.categorical_feature_column, "")).strip()
        candidates = [reference for reference in self.references if reference.category == category]
        if not candidates:
            raise FeatureValidationError("Scenario is not represented in the frozen model")
        nearest = min(
            candidates,
            key=lambda reference: sum(
                (value - reference_value) ** 2
                for value, reference_value in zip(transformed, reference.transformed_features)
            ),
        )
        distance = math.sqrt(
            sum(
                (value - reference_value) ** 2
                for value, reference_value in zip(transformed, nearest.transformed_features)
            )
        )
        fallback = _number(self.fallback_feature_column, values.get(self.fallback_feature_column), minimum=0)
        return nearest.target if distance <= self.maximum_normalized_distance else fallback

    def recommend(self, feature_input: RuntimeInput) -> tuple[float, int, str, str]:
        forecast = self.predict(feature_input)
        replicas, action, reason = self.policy.recommend(
            forecast, feature_input.current_replicas
        )
        return forecast, replicas, action, reason


def load_model_runtime(path: Path) -> CapacityModelRuntime:
    runtime = CapacityModelRuntime.from_directory(resolve_model_directory(path))
    runtime.recommend(RuntimeInput.from_environment())
    return runtime
