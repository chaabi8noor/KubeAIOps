#!/usr/bin/env python3
"""Build a versioned, leakage-safe capacity forecasting feature table."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "ml" / "capacity" / "src"))

from capacity_data.pipeline import read_csv, write_json
from capacity_features.pipeline import FeatureConfig, build_feature_rows, write_feature_rows


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def read_config(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--source-commit", default=current_commit())
    args = parser.parse_args()

    config = FeatureConfig.from_mapping(read_config(args.config))
    rows = build_feature_rows(read_csv(args.input), config)
    write_feature_rows(args.output, rows)
    split_counts = {
        split: sum(1 for row in rows if row["split"] == split)
        for split in ("train", "test")
    }
    write_json(
        args.metadata,
        {
            "feature_version": config.version,
            "source_dataset": str(args.input),
            "source_dataset_sha256": file_hash(args.input),
            "feature_config": str(args.config),
            "feature_config_sha256": file_hash(args.config),
            "source_commit": args.source_commit,
            "output_rows": len(rows),
            "split_counts": split_counts,
            "target_horizon_steps": config.horizon_steps,
            "rolling_window_steps": config.rolling_window_steps,
            "leakage_protection": "Training rows are selected by target timestamp, not feature timestamp.",
        },
    )


if __name__ == "__main__":
    main()
