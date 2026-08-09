#!/usr/bin/env python3
"""Package a frozen capacity model for the Capacity API image."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


REQUIRED_ARTIFACTS = (
    "model.json",
    "preprocessor.json",
    "model-version.json",
    "training-config.json",
    "training-metadata.json",
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--policy-config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    missing = [
        str(args.artifact_dir / name)
        for name in REQUIRED_ARTIFACTS
        if not (args.artifact_dir / name).is_file()
    ]
    if missing:
        raise ValueError(f"Frozen model artifacts are missing: {', '.join(missing)}")
    if not args.policy_config.is_file():
        raise ValueError(f"Replica-policy configuration is missing: {args.policy_config}")

    model = read_json(args.artifact_dir / "model.json")
    version = str(model.get("model_version", "")).strip()
    if not version:
        raise ValueError("Model artifact does not declare a version")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_ARTIFACTS:
        shutil.copyfile(args.artifact_dir / name, args.output_dir / name)
    shutil.copyfile(args.policy_config, args.output_dir / "replica-policy.yaml")
    manifest_files = (*REQUIRED_ARTIFACTS, "replica-policy.yaml")
    (args.output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "format_version": "capacity-api-model-package/v1",
                "model_version": version,
                "files": {name: file_hash(args.output_dir / name) for name in manifest_files},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
