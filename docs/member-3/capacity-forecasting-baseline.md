# Capacity forecasting baseline

This delivery adds a reproducible feature pipeline, a transparent persistence forecast, and a bounded replica recommendation policy. These components provide an explainable reference point before a primary model is trained.

## Pipeline

```text
validated capacity observations
  -> time-ordered feature rows
  -> explicit future demand target
  -> target-time train/test split
  -> persistence forecast
  -> replica recommendation
  -> saved evaluation evidence
```

Feature rows use the current request rate, a one-sample lag, a rolling request-rate mean, CPU utilisation, memory working set, latency, error ratio, current replicas, and scaling-event context. The target is the request rate at a configured future horizon. Feature history never crosses workload or scenario boundaries.

## Commands

```bash
make feature-build
make baseline-evaluate
make baseline-validation
```

The feature command writes `ml/capacity/data/features/capacity-features-v1.csv` and metadata that records input and configuration hashes. The baseline command saves predictions, error metrics, configuration hashes, a Markdown report, and an SVG forecast comparison in `ml/capacity/evaluation/baseline-v1/`.

## Replica policy

The policy is a pure recommendation layer. It accepts predicted requests per second and current replicas, applies a target-utilisation buffer and minimum/maximum bounds, then returns `scale_up`, `scale_down`, `hold`, or `insufficient_data`. It does not modify Kubernetes resources.

Independent tests cover low, moderate, high, sudden, falling, missing, invalid, and bounded inputs. The policy configuration is deliberately separate from both the forecast implementation and the Capacity API.

## Acceptance criteria

- The feature output is deterministic and leakage-safe.
- The baseline reads the processed dataset and writes forecasts, metrics, configuration evidence, and a plot.
- Identical inputs return identical forecasts and recommendations.
- Recommendations stay within configured replica bounds and require no Kubernetes credentials.
- The operational dashboard displays demand, forecast, recommendation, application health, scaling state, and recovery signals.
