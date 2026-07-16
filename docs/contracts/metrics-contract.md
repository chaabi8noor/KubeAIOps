# Member 3 Metrics Contract

| Field | Decision |
| --- | --- |
| Status | Proposed for Step 1 review |
| Owner | Member 3 - Capacity AIOps Engineer |
| Primary reviewer | Member 1 - Infrastructure AIOps Engineer |
| Change control | A reviewed merge request is required for a breaking change. |

## Purpose and scope

This contract fixes the metric vocabulary shared by the demo workload, Capacity API, Prometheus, the dataset pipeline, Grafana, and the load-validation scripts. It covers Member 3's capacity stream only.

Missing, stale, or unavailable input data must be represented as `unknown` by the Capacity API. It must never be silently converted to zero or used to generate an unsafe scale-down recommendation.

## Stable identity and collection decisions

| Item | Stable value |
| --- | --- |
| Metrics path | `/metrics` |
| Scrape interval | `15s` |
| Scrape timeout | `10s` |
| Namespace | `kubeaiops` |
| Capacity service | `capacity-api` |
| Demo workload | `demo-workload` |
| Capacity metric prefix | `kubeaiops_capacity_` |
| Workload metric prefix | `kubeaiops_workload_` |
| Time unit | seconds |
| Memory unit | bytes |
| CPU unit | cores |
| Traffic unit | requests per second |
| Latency representation | Prometheus histogram in seconds |

The local retention assumption is **7 days**. The shared-environment retention period is provisional until Member 1 confirms the Prometheus configuration.

## Kubernetes and Prometheus labels

Every Member 3 resource must include the following Kubernetes labels:

```yaml
app.kubernetes.io/name: capacity-api
app.kubernetes.io/component: capacity-management
app.kubernetes.io/part-of: kubeaiops
app.kubernetes.io/managed-by: Helm
app.kubernetes.io/version: "0.1.0"
```

The Capacity API may use only these labels on its own metric series unless a reviewed update adds another bounded label:

| Label | Required on | Allowed values / rule |
| --- | --- | --- |
| `namespace` | workload and capacity metrics | Kubernetes namespace, initially `kubeaiops` |
| `service` | API and workload metrics | stable service name |
| `workload` | capacity decision metrics | DNS-label workload name |
| `status` | API request metrics | HTTP status code |
| `method` | API request metrics | HTTP method |
| `route` | API request metrics | route template, never a raw URL |
| `model_version` | prediction and recommendation metrics | fixed loaded model version |
| `scenario` | test-generated workload metrics | `normal`, `progressive`, `spike`, `sustained`, or `recovery` |
| `reason` | failure metrics only | controlled error code from the API contract |

Request IDs, timestamps, user IDs, raw error text, Pod UIDs, IP addresses, and full URLs are forbidden as label values. Pod names are not labels on Member 3's custom metrics; aggregate by the stable workload label instead.

## Metric catalogue

| Metric | Type | Unit | Required labels | Meaning |
| --- | --- | --- | --- | --- |
| `kubeaiops_capacity_api_requests_total` | Counter | requests | `namespace`, `service`, `method`, `route`, `status` | Recommendation API requests received. |
| `kubeaiops_capacity_api_request_duration_seconds` | Histogram | seconds | `namespace`, `service`, `method`, `route`, `status` | API response-time distribution. Bucket boundaries are provisional until the first k6 baseline. |
| `kubeaiops_capacity_predictions_total` | Counter | predictions | `namespace`, `workload`, `model_version` | Successful forecasts produced. |
| `kubeaiops_capacity_prediction_failures_total` | Counter | failures | `namespace`, `workload`, `model_version`, `reason` | Failed predictions grouped by a controlled reason. |
| `kubeaiops_capacity_forecast_requests_per_second` | Gauge | requests/second | `namespace`, `workload`, `model_version` | Forecast traffic at the configured horizon. |
| `kubeaiops_capacity_recommended_replicas` | Gauge | replicas | `namespace`, `workload`, `model_version` | Replica count recommended by the policy. |
| `kubeaiops_capacity_current_replicas` | Gauge | replicas | `namespace`, `workload` | Latest observed available-replica count used by the policy. |
| `kubeaiops_capacity_recommendation_gap` | Gauge | replicas | `namespace`, `workload`, `model_version` | Recommended replicas minus current available replicas. |
| `kubeaiops_capacity_model_info` | Gauge | constant `1` | `model_name`, `model_version` | Loaded model identity. |
| `kubeaiops_capacity_metrics_source_failures_total` | Counter | failures | `namespace`, `workload`, `reason` | Failures while retrieving workload metrics. |
| `kubeaiops_workload_requests_total` | Counter | requests | `namespace`, `service`, `workload`, `method`, `route`, `status`, `scenario` | Requests served by the demo workload. |
| `kubeaiops_workload_request_duration_seconds` | Histogram | seconds | `namespace`, `service`, `workload`, `method`, `route`, `status`, `scenario` | Demo-workload latency distribution. |
| `kubeaiops_workload_errors_total` | Counter | errors | `namespace`, `service`, `workload`, `scenario` | Demo-workload request failures. |

The initial Capacity API histogram bucket boundaries are provisional. They must be fixed after the normal-load k6 baseline and recorded in the model and validation documentation.

## Derived data and recording rules

Member 3's PromQL and recording rules live under `monitoring/capacity/`. The following stable recording-rule names are reserved:

```text
kubeaiops:capacity:request_rate_5m
kubeaiops:capacity:p95_latency_5m
kubeaiops:capacity:error_ratio_5m
kubeaiops:capacity:recommendation_gap
```

The feature pipeline must record the query version, collection interval, source, scenario, start and end time, and the missing-data handling applied to each exported dataset. Input data must be time-aligned before model training or evaluation.

## Data quality rules

- Treat an input as stale when its newest sample is older than two scrape intervals (30 seconds) at decision time.
- Preserve missing values during extraction; imputation, if later justified, must be deterministic and documented in the feature pipeline.
- Reject non-finite values, duplicate timestamps, incompatible units, and invalid replica counts during dataset validation.
- The model must use the same feature names, units, and ordering during training and serving.

## Approval checklist

- [ ] Member 1 confirms the scrape and discovery conventions.
- [ ] All three members approve the stable prefixes, labels, units, and missing-data behavior.
- [ ] Member 3 records the initial histogram buckets and shared retention period once measured or confirmed.
