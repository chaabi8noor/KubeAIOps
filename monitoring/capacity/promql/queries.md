# Capacity PromQL catalogue

These Week 2 queries use the stable names from the Member 3 metrics contract. An empty result means that Prometheus has not scraped the matching service yet; it must not be interpreted as zero traffic or safe capacity.

| Query | Purpose | Unit | Required labels |
| --- | --- | --- | --- |
| `sum by (workload) (rate(kubeaiops_workload_requests_total{namespace="kubeaiops",service="demo-workload"}[5m]))` | Incoming demo workload rate | requests/second | `namespace`, `service`, `workload` |
| `histogram_quantile(0.95, sum by (le) (rate(kubeaiops_workload_request_duration_seconds_bucket{namespace="kubeaiops",service="demo-workload"}[5m])))` | Demo workload p95 latency | seconds | `namespace`, `service` |
| `sum(rate(kubeaiops_workload_errors_total{namespace="kubeaiops",service="demo-workload"}[5m])) / clamp_min(sum(rate(kubeaiops_workload_requests_total{namespace="kubeaiops",service="demo-workload"}[5m])), 1)` | Demo workload error ratio | ratio | `namespace`, `service` |
| `sum(rate(kubeaiops_capacity_api_requests_total{namespace="kubeaiops",service="capacity-api"}[5m]))` | Capacity API recommendation rate | requests/second | `namespace`, `service` |
| `kubeaiops_capacity_recommendation_gap{namespace="kubeaiops",workload="demo-workload"}` | Difference between recommended and current replicas | replicas | `namespace`, `workload`, `model_version` |

The corresponding recording rules are in `recording-rules.yaml`. They remain a Prometheus configuration input until Member 1 supplies the shared Prometheus deployment convention.
