# Capacity data pipeline

The data-preparation phase creates a reproducible dataset for the Capacity AIOps stream. The checked-in `v1` sample is deterministic scenario data; it validates the schema and pipeline without pretending to be a production trace. Replace or supplement it with exports collected from the project Prometheus instance before baseline model development.

## Dataset schema

Each observation records an RFC3339 UTC timestamp, workload, request rate, CPU ratio, memory working set, p95 latency, error ratio, replicas, scaling event, scenario, collection interval, data source, and run status. The canonical field order and units are in `src/capacity_data/schema.py`; a portable schema is in `schema/observations-v1.schema.json`.

## Reproduce the checked-in dataset

From the repository root:

```bash
make data-pipeline
make data-validate
```

This deterministically creates five raw scenario files under `data/raw/`, cleans them into `data/processed/capacity-observations-v1.csv`, and writes the validation report and dataset version record beside it.

## Collect from Prometheus

The query set is versioned in `config/prometheus-queries.json`. Supply an explicit time range and scenario after a completed load test:

```bash
make extract-prometheus \
  PROMETHEUS_URL=http://127.0.0.1:9090 \
  EXTRACT_SCENARIO=normal \
  EXTRACT_START=2026-07-25T09:00:00Z \
  EXTRACT_END=2026-07-25T09:20:00Z
```

The extractor uses `query_range`, aligns samples to timestamps, preserves absent values for validation, and saves both the raw CSV and its collection configuration under `data/raw/prometheus/`. That directory is intentionally ignored because it may contain large environment-specific collections.

## Validation boundary

The validation scope checks field presence, duplicate timestamps, numerical ranges and units, scenario labels, interval consistency, scenario boundaries, replica alignment, and failed runs.

## Feature preparation and baseline validation

The feature pipeline converts validated observations into a deterministic, time-ordered table with lagged and rolling request-rate features. Forecast targets are stored at an explicit future timestamp, and the train/test split is selected by target time to prevent leakage.

```bash
make feature-build
make baseline-evaluate
```

`config/features.yaml` controls the window, horizon, and split. `config/baseline.yaml` defines the transparent persistence baseline, while `config/replica-policy.yaml` defines bounded recommendation behaviour. The evaluation saves predictions, metrics, the exact configuration hashes, and an SVG forecast comparison under `evaluation/baseline-v1/`.
