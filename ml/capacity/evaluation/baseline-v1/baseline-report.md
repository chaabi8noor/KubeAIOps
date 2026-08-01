# Persistence baseline validation

The persistence baseline forecasts the next demand sample from the latest observed request rate. It is a transparent benchmark for later forecasting models, not an operational control loop.

## Evaluation metrics

| Metric | Value |
| --- | ---: |
| Test samples | 45 |
| MAE (requests/second) | 0.0504 |
| RMSE (requests/second) | 0.0591 |
| MAPE (%) | 0.0938 |
| Under-provisioned recommendations | 0 |
| Over-provisioned recommendations | 0 |

## Recommendation actions

- `hold`: 40
- `scale_up`: 5

## Limitations

- The sample dataset is deterministic scenario data and must be replaced with observed Prometheus exports before selecting an operational model.
- The policy returns recommendations only; Kubernetes changes remain outside this component.
- The baseline uses no seasonality, trend, or external signals.
