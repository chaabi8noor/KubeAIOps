# Member 3 capacity data pipeline

This phase completes repeatable capacity-load scenarios and produces a validated starter dataset. It does not train a model or add forecasting features; those belong to the model-development phase.

## Load scenarios

Each k6 scenario has bounded inputs, a scenario header on every workload request, thresholds, a machine-readable summary, and a stage report with timestamps.

| Scenario | Command | Default shape |
| --- | --- | --- |
| Normal | `make load-normal` | 12 requests/second for 30 seconds |
| Progressive | `make load-progressive` | 10 -> 30 -> 60 -> 90 requests/second in 20-second stages |
| Spike | `make load-spike` | baseline -> 120 requests/second spike -> baseline |
| Sustained | `make load-sustained` | 75 requests/second for two minutes |
| Recovery | `make test-recovery` | continuous traffic while one demo-workload pod is replaced |

Load summaries are written under `docs/evidence/member-3/load-tests/`; recovery evidence is under `docs/evidence/member-3/recovery/`. Both are ignored by Git because they are run-specific evidence. The recovery runner refuses a non-Kind context unless `ALLOW_NON_KIND=true` is deliberately supplied.

`make test-recovery` uses `kind-kubeaiops` by default. Override `KUBE_CONTEXT` only when the target cluster and its pod-deletion approval have been confirmed.

## Dataset flow

```text
scenario run or Prometheus query_range
  -> raw CSV with collection metadata
  -> deterministic cleaning and timestamp ordering
  -> validation report
  -> processed capacity-observations-v1.csv
```

The stable schema includes timestamp, workload name, request rate, CPU and memory usage, p95 latency, error ratio, replica count, scaling event, scenario label, collection interval, source, and test status. `ml/capacity/config/prometheus-queries.json` defines the query set used by the live extractor.

## Reproduce the starter data

```bash
make setup-test-env
make test
make data-pipeline
make data-validate
```

The committed v1 files are deterministic scenario profiles, clearly labelled `deterministic-scenario-profile-v1`. They are suitable for proving the pipeline and tests; they must be replaced with Prometheus exports before baseline evaluation.

## Completion criteria

- All five load scenarios are versioned and non-interactive.
- Every scenario produces a summary and configuration-derived report.
- The pipeline can create raw, processed, validation, and version-record artifacts from a clean checkout.
- Dataset validation rejects missing first observations, inconsistent intervals, invalid ranges, failed runs, and incomplete scenario coverage.
