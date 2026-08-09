# Primary model comparison

`capacity-primary-v1` is selected for API integration because its MAE is lower than the persistence baseline.

## Forecast accuracy

| Metric | Persistence baseline | Primary model |
| --- | ---: | ---: |
| MAE (requests/second) | 0.7191 | 0.0273 |
| RMSE (requests/second) | 4.4644 | 0.0426 |
| MAPE (%) | 1.0205 | 0.1169 |
| Under-provisioned samples | 1 | 0 |
| Over-provisioned samples | 0 | 0 |

## Scenario stability

| Scenario | Samples | MAE | RMSE | MAPE (%) |
| --- | ---: | ---: | ---: | ---: |
| normal | 9 | 0.0223 | 0.0485 | 0.1887 |
| progressive | 9 | 0.0371 | 0.0424 | 0.0437 |
| recovery | 9 | 0.0184 | 0.0334 | 0.0385 |
| spike | 9 | 0.0408 | 0.0482 | 0.2920 |
| sustained | 9 | 0.0177 | 0.0387 | 0.0216 |

## Recommendation stability

| Action | Samples |
| --- | ---: |
| hold | 18 |
| scale_down | 18 |
| scale_up | 9 |

Repeated predictions and recommendations returned identical values for the same evaluation input.

## Limitations and operational interpretation

- This model was trained on deterministic scenario data; observed Prometheus exports are required before any production threshold change.
- The result is an explainable forecast and bounded recommendation, not a direct Kubernetes scaling command.
- Prediction failures are handled by the API without changing Kubernetes state.
