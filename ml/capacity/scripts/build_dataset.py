#!/usr/bin/env python3
"""Clean raw capacity observations and create the Week 3 processed dataset."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "capacity" / "src"))

from capacity_data.pipeline import clean_rows, read_csv, validate_rows, write_csv, write_json
from capacity_data.schema import SCHEMA_VERSION


def current_commit() -> str:
    """Return the source commit without making Git a runtime dependency in tests."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--processed-output", type=Path, required=True)
    parser.add_argument("--validation-report", type=Path, required=True)
    parser.add_argument("--version-record", type=Path, required=True)
    parser.add_argument("--dataset-version", default="capacity-observations-v1")
    parser.add_argument("--collection-date", default=date.today().isoformat())
    parser.add_argument("--source-commit", default=current_commit())
    parser.add_argument("--scenario-version", default="load-scenarios-v1")
    parser.add_argument("--query-version", default="promql-v1")
    parser.add_argument("--pipeline-version", default="1.0.0")
    args = parser.parse_args()

    paths = sorted(args.raw_dir.glob("*.csv"))
    if not paths:
        parser.error(f"No CSV files found in {args.raw_dir}")
    raw_rows = [row for path in paths for row in read_csv(path)]
    cleaned = clean_rows(raw_rows)
    validation = validate_rows(cleaned.rows)
    validation["cleaning"] = {
        "input_records": len(raw_rows),
        "output_records": len(cleaned.rows),
        "forward_filled_values": cleaned.filled_values,
        "removed_exact_duplicates": cleaned.removed_duplicates,
    }
    validation["source_files"] = [path.name for path in paths]

    write_csv(args.processed_output, cleaned.rows)
    write_json(args.validation_report, validation)
    write_json(
        args.version_record,
        {
            "dataset_version": args.dataset_version,
            "schema_version": SCHEMA_VERSION,
            "source_commit": args.source_commit,
            "collection_date": args.collection_date,
            "scenario_version": args.scenario_version,
            "query_version": args.query_version,
            "pipeline_version": args.pipeline_version,
            "raw_inputs": [path.name for path in paths],
            "processed_records": len(cleaned.rows),
            "known_limitations": [
                "The checked-in v1 dataset is deterministic synthetic starter data, not an observed production trace.",
                "Feature windows, prediction targets, and train/test splitting are deferred to Week 4.",
                "A Prometheus collection must be repeated after each real load campaign before evaluating a model.",
            ],
        },
    )


if __name__ == "__main__":
    main()
