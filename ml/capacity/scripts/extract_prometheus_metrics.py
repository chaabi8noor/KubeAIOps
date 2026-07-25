#!/usr/bin/env python3
"""Export a timestamp-aligned raw dataset from the Prometheus HTTP API."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "capacity" / "src"))

from capacity_data.pipeline import write_csv, write_json
from capacity_data.schema import DATASET_COLUMNS, SCENARIOS, format_timestamp


def parse_api_timestamp(value: str | float) -> str:
    return format_timestamp(datetime.fromtimestamp(float(value), tz=timezone.utc))


def fetch_range(base_url: str, query: str, start: str, end: str, step: str) -> list[dict[str, object]]:
    query_string = urlencode({"query": query, "start": start, "end": end, "step": step})
    url = f"{base_url.rstrip('/')}/api/v1/query_range?{query_string}"
    with urlopen(url, timeout=30) as response:  # nosec B310 - URL is an explicit operator input
        payload = json.load(response)
    if payload.get("status") != "success":
        raise RuntimeError(f"Prometheus query failed: {payload}")
    return payload.get("data", {}).get("result", [])


def align_series(results: list[dict[str, object]]) -> dict[str, float]:
    """Sum all matching series per timestamp for one documented query."""
    totals: dict[str, float] = defaultdict(float)
    for result in results:
        for timestamp, value in result.get("values", []):
            totals[parse_api_timestamp(timestamp)] += float(value)
    return dict(totals)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus-url", required=True)
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--start", required=True, help="RFC3339 UTC start time")
    parser.add_argument("--end", required=True, help="RFC3339 UTC end time")
    parser.add_argument("--step", default="30s")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    parser.add_argument("--workload", default="demo-workload")
    parser.add_argument("--collection-interval-seconds", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config-output", type=Path, required=True)
    args = parser.parse_args()
    if args.collection_interval_seconds <= 0:
        parser.error("--collection-interval-seconds must be positive")

    config_text = args.queries.read_text(encoding="utf-8")
    config = json.loads(config_text)
    queries = config.get("queries", [])
    if not queries:
        parser.error("The query configuration contains no queries")

    columns: dict[str, dict[str, float]] = {}
    for item in queries:
        column = item["column"]
        columns[column] = align_series(
            fetch_range(args.prometheus_url, item["query"], args.start, args.end, args.step)
        )

    timestamps = sorted({timestamp for values in columns.values() for timestamp in values})
    if not timestamps:
        raise RuntimeError("Prometheus returned no samples for the requested time range")

    rows: list[dict[str, str]] = []
    for timestamp in timestamps:
        rows.append(
            {
                "timestamp": timestamp,
                "workload": args.workload,
                "requests_per_second": str(columns.get("requests_per_second", {}).get(timestamp, "")),
                "cpu_utilization_ratio": str(columns.get("cpu_utilization_ratio", {}).get(timestamp, "")),
                "memory_working_set_bytes": str(columns.get("memory_working_set_bytes", {}).get(timestamp, "")),
                "p95_latency_seconds": str(columns.get("p95_latency_seconds", {}).get(timestamp, "")),
                "error_ratio": str(columns.get("error_ratio", {}).get(timestamp, "")),
                "replicas": str(columns.get("replicas", {}).get(timestamp, "")),
                "scaling_event": "none",
                "scenario": args.scenario,
                "collection_interval_seconds": str(args.collection_interval_seconds),
                "data_source": "prometheus-query-range",
                "run_status": "passed",
            }
        )
    write_csv(args.output, rows)
    write_json(
        args.config_output,
        {
            "schema_version": "1.0.0",
            "prometheus_url": args.prometheus_url,
            "start": args.start,
            "end": args.end,
            "step": args.step,
            "scenario": args.scenario,
            "workload": args.workload,
            "collection_interval_seconds": args.collection_interval_seconds,
            "query_config": str(args.queries),
            "query_config_sha256": hashlib.sha256(config_text.encode("utf-8")).hexdigest(),
            "columns": [item["column"] for item in queries],
            "output_columns": list(DATASET_COLUMNS),
        },
    )


if __name__ == "__main__":
    main()
