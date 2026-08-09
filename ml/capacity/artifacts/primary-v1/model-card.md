# Capacity primary model card

## Model identity

- Version: `capacity-primary-v1`
- Method: `adaptive_nearest_neighbor`

## Intended use

Forecast the configured short horizon of workload requests per second and provide evidence to the separate replica recommendation policy.

## Inputs and outputs

- Inputs: `current_requests_per_second`, `request_rate_lag_1`, `request_rate_rolling_mean`, `cpu_utilization_ratio`, `p95_latency_seconds`, `error_ratio`, `current_replicas`
- Output: finite, non-negative forecast requests per second.
- Operational result: a bounded recommendation from the independent replica policy.

## Training and evaluation

- Dataset: `capacity-observations-v1`
- Split: feature rows are separated by target timestamp before model training.
- Test MAE: 0.0273 requests/second
- Test RMSE: 0.0426 requests/second
- Test MAPE: 0.1169%

## Limitations and failure conditions

- Deterministic scenario data does not replace observed production traffic.
- Missing, non-numeric, or non-finite inputs must fail the prediction path safely.
- The model is not an authority to mutate Kubernetes resources.

## Versioning process

A frozen release includes model, preprocessor, feature order, configuration, dataset identity, evaluation report, and source commit. Any input or configuration change requires a new model version and comparison run.
