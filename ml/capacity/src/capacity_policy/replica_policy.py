"""Convert a demand forecast into a bounded, explainable recommendation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping


class ReplicaPolicyConfigurationError(ValueError):
    """Raised when a replica-policy configuration is invalid."""


@dataclass(frozen=True)
class ReplicaPolicyConfig:
    version: str
    minimum_replicas: int
    maximum_replicas: int
    requests_per_second_per_replica: float
    target_utilization: float
    downscale_tolerance: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ReplicaPolicyConfig":
        try:
            config = cls(
                version=str(value["version"]),
                minimum_replicas=int(value["minimum_replicas"]),
                maximum_replicas=int(value["maximum_replicas"]),
                requests_per_second_per_replica=float(value["requests_per_second_per_replica"]),
                target_utilization=float(value["target_utilization"]),
                downscale_tolerance=float(value["downscale_tolerance"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ReplicaPolicyConfigurationError("Invalid replica-policy configuration") from error
        if not config.version:
            raise ReplicaPolicyConfigurationError("Replica-policy configuration requires a version")
        if config.minimum_replicas < 1 or config.maximum_replicas < config.minimum_replicas:
            raise ReplicaPolicyConfigurationError("Replica bounds are invalid")
        if config.requests_per_second_per_replica <= 0:
            raise ReplicaPolicyConfigurationError("requests_per_second_per_replica must be positive")
        if not 0 < config.target_utilization <= 1:
            raise ReplicaPolicyConfigurationError("target_utilization must be in (0, 1]")
        if not 0 <= config.downscale_tolerance < 1:
            raise ReplicaPolicyConfigurationError("downscale_tolerance must be in [0, 1)")
        return config


@dataclass(frozen=True)
class Recommendation:
    replicas: int
    action: str
    reason: str


class ReplicaPolicy:
    """A pure policy layer; it only recommends, never mutates Kubernetes."""

    def __init__(self, config: ReplicaPolicyConfig):
        self.config = config

    @property
    def effective_capacity_per_replica(self) -> float:
        return (
            self.config.requests_per_second_per_replica * self.config.target_utilization
        )

    def recommend(
        self, predicted_requests_per_second: float | None, current_replicas: int
    ) -> Recommendation:
        current = min(
            self.config.maximum_replicas,
            max(self.config.minimum_replicas, int(current_replicas)),
        )
        if (
            predicted_requests_per_second is None
            or not isinstance(predicted_requests_per_second, (int, float))
            or not math.isfinite(predicted_requests_per_second)
            or predicted_requests_per_second < 0
        ):
            return Recommendation(
                replicas=current,
                action="insufficient_data",
                reason="A finite non-negative demand forecast is required.",
            )

        required = math.ceil(
            predicted_requests_per_second / self.effective_capacity_per_replica
        )
        desired = min(
            self.config.maximum_replicas,
            max(self.config.minimum_replicas, required),
        )
        if desired > current:
            return Recommendation(
                replicas=desired,
                action="scale_up",
                reason="Predicted demand exceeds the safe capacity of current replicas.",
            )
        downscale_threshold = (
            current
            * self.effective_capacity_per_replica
            * (1 - self.config.downscale_tolerance)
        )
        if desired < current and predicted_requests_per_second <= downscale_threshold:
            return Recommendation(
                replicas=desired,
                action="scale_down",
                reason="Predicted demand remains below the guarded downscale threshold.",
            )
        return Recommendation(
            replicas=current,
            action="hold",
            reason="Predicted demand is within the guarded capacity range.",
        )
