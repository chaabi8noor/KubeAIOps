#!/usr/bin/env python3
"""Create deterministic sample observations for every load scenario."""

from __future__ import annotations

import argparse
import math
import sys
from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "capacity" / "src"))

from capacity_data.pipeline import write_csv, write_json
from capacity_data.schema import DATASET_COLUMNS, format_timestamp, parse_timestamp


SCENARIO_ORDER = ("normal", "progressive", "spike", "sustained", "recovery")


def profile_for(scenario: str, index: int, points: int) -> tuple[float, float, int, float, float, str]:
    """Return rate, CPU, replicas, latency, errors, and scaling event."""
    wave = math.sin(index / 3) * 0.02
    if scenario == "normal":
        return 12 + wave * 10, 0.35 + wave, 2, 0.045 + abs(wave) / 4, 0.001, "none"
    if scenario == "progressive":
        stage = min(3, index * 4 // points)
        rates = (10, 28, 55, 85)
        cpus = (0.28, 0.45, 0.66, 0.78)
        replicas = (2, 2, 3, 4)
        event = "scale_up" if index and index * 4 % points == 0 and stage > 1 else "none"
        return rates[stage] + wave * 5, cpus[stage] + wave, replicas[stage], 0.05 + stage * 0.03, 0.002, event
    if scenario == "spike":
        spike_start, spike_end = points // 3, (points * 2) // 3
        if spike_start <= index < spike_end:
            event = "scale_up" if index == spike_start else "none"
            return 120 + wave * 10, 0.9 + wave / 2, 5, 0.22 + abs(wave), 0.012, event
        event = "scale_down" if index == spike_end else "none"
        replicas = 3 if index >= spike_end else 2
        return 14 + wave * 5, 0.34 + wave, replicas, 0.052, 0.002, event
    if scenario == "sustained":
        return 82 + wave * 8, 0.76 + wave, 4, 0.12 + abs(wave), 0.004, "none"
    if scenario == "recovery":
        failure_start, failure_end = points // 2, points // 2 + max(2, points // 8)
        if failure_start <= index < failure_end:
            event = "pod_replacement" if index == failure_start else "none"
            return 48, 0.68, 2, 0.35, 0.15, event
        replicas = 3 if index >= failure_end else 3
        return 48 + wave * 6, 0.64 + wave, replicas, 0.09, 0.004, "none"
    raise ValueError(f"Unsupported scenario: {scenario}")


def rows_for_scenario(
    scenario: str,
    start: str,
    points: int,
    interval_seconds: int,
) -> list[dict[str, str]]:
    started_at = parse_timestamp(start)
    rows: list[dict[str, str]] = []
    for index in range(points):
        rate, cpu, replicas, latency, error_ratio, scaling_event = profile_for(
            scenario, index, points
        )
        timestamp = started_at + timedelta(seconds=index * interval_seconds)
        rows.append(
            {
                "timestamp": format_timestamp(timestamp),
                "workload": "demo-workload",
                "requests_per_second": f"{rate:.3f}",
                "cpu_utilization_ratio": f"{min(cpu, 0.99):.3f}",
                "memory_working_set_bytes": str(int(180_000_000 + cpu * 140_000_000)),
                "p95_latency_seconds": f"{latency:.3f}",
                "error_ratio": f"{error_ratio:.3f}",
                "replicas": str(replicas),
                "scaling_event": scaling_event,
                "scenario": scenario,
                "collection_interval_seconds": str(interval_seconds),
                "data_source": "deterministic-scenario-profile-v1",
                "run_status": "passed",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start", default="2026-07-25T09:00:00Z")
    parser.add_argument("--points", type=int, default=40)
    parser.add_argument("--interval-seconds", type=int, default=30)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if args.points < 8 or args.interval_seconds <= 0:
        parser.error("--points must be at least 8 and --interval-seconds must be positive")

    first_start = parse_timestamp(args.start)
    files: list[dict[str, object]] = []
    for scenario_index, scenario in enumerate(SCENARIO_ORDER):
        scenario_start = first_start + timedelta(
            seconds=scenario_index * (args.points + 2) * args.interval_seconds
        )
        rows = rows_for_scenario(
            scenario, format_timestamp(scenario_start), args.points, args.interval_seconds
        )
        path = args.output_dir / f"{scenario}.csv"
        write_csv(path, rows)
        files.append({"path": path.name, "scenario": scenario, "records": len(rows)})

    write_json(
        args.output_dir / "manifest-v1.json",
        {
            "schema_version": "1.0.0",
            "dataset_seed": "deterministic-scenario-profile-v1",
            "source_commit": args.source_commit,
            "collection_start": format_timestamp(first_start),
            "collection_interval_seconds": args.interval_seconds,
            "records_per_scenario": args.points,
            "columns": list(DATASET_COLUMNS),
            "files": files,
            "limitation": "This checked-in starter dataset is deterministic synthetic data. Replace it with Prometheus exports before model evaluation.",
        },
    )


if __name__ == "__main__":
    main()
