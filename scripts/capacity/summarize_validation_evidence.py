#!/usr/bin/env python3
"""Convert local k6 outputs into a compact, reviewable validation record."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCENARIOS = {
    "normal": {
        "summary": Path("docs/evidence/member-3/load-tests/normal-summary.json"),
        "report": Path("docs/evidence/member-3/load-tests/normal-report.json"),
        "expected": "Controlled traffic completes without failed requests and keeps p95 latency below 1000 ms.",
    },
    "progressive": {
        "summary": Path("docs/evidence/member-3/load-tests/progressive-summary.json"),
        "report": Path("docs/evidence/member-3/load-tests/progressive-report.json"),
        "expected": "Traffic ramps through the configured stages while the API remains reachable.",
    },
    "spike": {
        "summary": Path("docs/evidence/member-3/load-tests/spike-summary.json"),
        "report": Path("docs/evidence/member-3/load-tests/spike-report.json"),
        "expected": "A transient spike completes without failed requests and returns to the configured baseline.",
    },
    "sustained": {
        "summary": Path("docs/evidence/member-3/load-tests/sustained-summary.json"),
        "report": Path("docs/evidence/member-3/load-tests/sustained-report.json"),
        "expected": "High traffic remains healthy for the configured duration without latency-threshold failure.",
    },
    "pod-failure": {
        "summary": Path("docs/evidence/member-3/recovery/k6-summary.json"),
        "report": Path("docs/evidence/member-3/recovery/recovery-report.json"),
        "expected": "Traffic continues while Kubernetes replaces one demo-workload pod within the recovery window.",
    },
}


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def value(data: dict[str, Any], metric: str, field: str) -> Any:
    return data.get("metrics", {}).get(metric, {}).get(field)


def check_counts(group: dict[str, Any]) -> tuple[int, int]:
    passed = 0
    failed = 0
    for check in group.get("checks", {}).values():
        passed += int(check.get("passes", 0))
        failed += int(check.get("fails", 0))
    for child in group.get("groups", {}).values():
        child_passed, child_failed = check_counts(child)
        passed += child_passed
        failed += child_failed
    return passed, failed


def current_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def scenario_record(root: Path, name: str, definition: dict[str, Path | str]) -> dict[str, Any]:
    summary_path = root / definition["summary"]
    report_path = root / definition["report"]
    summary = load_json(summary_path)
    report = load_json(report_path)
    record: dict[str, Any] = {
        "scenario": name,
        "expected_result": definition["expected"],
        "summary_source": str(definition["summary"]),
        "report_source": str(definition["report"]),
    }

    if summary is None:
        record.update(status="not-run", conclusion="No k6 summary was found.")
        return record

    checks_passed, checks_failed = check_counts(summary.get("root_group", {}))
    failed_request_rate = value(summary, "http_req_failed", "value")
    p95_ms = value(summary, "http_req_duration", "p(95)")
    record["metrics"] = {
        "http_request_count": value(summary, "http_reqs", "count"),
        "http_request_rate_per_second": value(summary, "http_reqs", "rate"),
        "http_failed_request_rate": failed_request_rate,
        "http_request_duration_p95_ms": p95_ms,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
    }
    if report is not None:
        record["stages"] = report.get("stages", [])
        record["started_at"] = report.get("started_at")
        if name == "pod-failure":
            record["recovery"] = {
                key: report.get(key)
                for key in ("context", "namespace", "victim_pod", "replacement_pod", "deleted_at", "recovered_at")
            }

    if name == "pod-failure" and report is None:
        record.update(
            status="incomplete",
            conclusion="Traffic evidence exists, but the pod replacement record is missing; rerun the protected recovery test.",
        )
    elif failed_request_rate == 0 and checks_failed == 0 and (p95_ms is None or p95_ms < 1000):
        record.update(status="passed", conclusion="All observed request and check criteria passed.")
    else:
        record.update(status="failed", conclusion="Inspect the raw k6 summary before accepting this scenario.")
    return record


def markdown(records: list[dict[str, Any]], commit: str) -> str:
    lines = [
        "# Capacity validation summary",
        "",
        f"Source commit: `{commit}`.",
        "",
        "This file is generated from local k6 output. It records measured results; it does not replace dashboard or alert review.",
        "",
        "| Scenario | Status | Requests | Failed-request rate | p95 latency (ms) | Checks |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for record in records:
        metrics = record.get("metrics", {})
        checks = f"{metrics.get('checks_passed', '—')} passed / {metrics.get('checks_failed', '—')} failed"
        lines.append(
            "| {scenario} | {status} | {requests} | {failure_rate} | {p95} | {checks} |".format(
                scenario=record["scenario"],
                status=record["status"],
                requests=metrics.get("http_request_count", "—"),
                failure_rate=metrics.get("http_failed_request_rate", "—"),
                p95=metrics.get("http_request_duration_p95_ms", "—"),
                checks=checks,
            )
        )
    lines.extend(
        [
            "",
            "A `not-run` or `incomplete` result is an evidence gap, not a passing result.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    records = [scenario_record(root, name, definition) for name, definition in SCENARIOS.items()]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_commit": current_commit(root),
        "scenarios": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown(records, payload["source_commit"]), encoding="utf-8")


if __name__ == "__main__":
    main()
