from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ml" / "capacity" / "src"))

from capacity_policy.replica_policy import ReplicaPolicy, ReplicaPolicyConfig


def policy() -> ReplicaPolicy:
    return ReplicaPolicy(
        ReplicaPolicyConfig.from_mapping(
            {
                "version": "replica-policy-test",
                "minimum_replicas": 1,
                "maximum_replicas": 6,
                "requests_per_second_per_replica": 30,
                "target_utilization": 0.7,
                "downscale_tolerance": 0.15,
            }
        )
    )


def test_policy_handles_low_moderate_and_high_pressure() -> None:
    assert policy().recommend(10, 3).action == "scale_down"
    assert policy().recommend(35, 2).action == "hold"
    high = policy().recommend(100, 2)
    assert high.action == "scale_up"
    assert high.replicas == 5


def test_policy_handles_sudden_falling_and_bounded_demand() -> None:
    assert policy().recommend(125, 2).replicas == 6
    assert policy().recommend(12, 5).replicas == 1
    assert policy().recommend(500, 2).replicas == 6
    assert policy().recommend(0, 1).replicas == 1


def test_policy_preserves_current_capacity_for_missing_or_invalid_forecasts() -> None:
    assert policy().recommend(None, 3).action == "insufficient_data"
    assert policy().recommend(math.nan, 3).action == "insufficient_data"
    assert policy().recommend(-1, 3).replicas == 3
