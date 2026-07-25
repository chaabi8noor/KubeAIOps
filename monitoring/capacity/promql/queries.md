# Capacity PromQL catalogue

These Week 2 queries use the stable names from the Member 3 metrics contract. An empty result means that Prometheus has not scraped the matching service yet; it must not be interpreted as zero traffic or safe capacity.

| Query | Purpose | Unit | Required labels |
| --- | --- | --- | --- |
| `sum by (workload) (rate(kubeaiops_workload_requests_total{namespace="kubeaiops",service="demo-workload"}[5m]))` | Incoming demo workload rate | requests/second | `namespace`, `service`, `workload` |
| `histogram_quantile(0.95, sum by (le) (rate(kubeaiops_workload_request_duration_seconds_bucket{namespace="kubeaiops",service="demo-workload"}[5m])))` | Demo workload p95 latency | seconds | `namespace`, `service` |
| `sum(rate(kubeaiops_workload_errors_total{namespace="kubeaiops",service="demo-workload"}[5m])) / clamp_min(sum(rate(kubeaiops_workload_requests_total{namespace="kubeaiops",service="demo-workload"}[5m])), 1)` | Demo workload error ratio | ratio | `namespace`, `service` |
| `sum(rate(kubeaiops_capacity_api_requests_total{namespace="kubeaiops",service="capacity-api"}[5m]))` | Capacity API recommendation rate | requests/second | `namespace`, `service` |
| `kubeaiops_capacity_recommendation_gap{namespace="kubeaiops",workload="demo-workload"}` | Difference between recommended and current replicas | replicas | `namespace`, `workload`, `model_version` |
| `count(kube_pod_status_ready{namespace="kubeaiops",condition="true",pod=~"demo-workload-.*"})` | Ready demo-workload replicas for dataset alignment | replicas | `namespace`, `pod`, `condition` |
| `sum(rate(container_cpu_usage_seconds_total{namespace="kubeaiops",pod=~"demo-workload-.*",container!=""}[5m])) / clamp_min(sum(kube_pod_container_resource_limits{namespace="kubeaiops",pod=~"demo-workload-.*",container!="",resource="cpu",unit="core"}), 0.001)` | Demo-workload CPU utilization relative to requested CPU limit | ratio | `namespace`, `pod`, `container`, `resource`, `unit` |
| `sum(container_memory_working_set_bytes{namespace="kubeaiops",pod=~"demo-workload-.*",container!=""})` | Demo-workload memory working set | bytes | `namespace`, `pod`, `container` |

The corresponding recording rules are in `recording-rules.yaml`. They remain a Prometheus configuration input until Member 1 supplies the shared Prometheus deployment convention.

`ml/capacity/config/prometheus-queries.json` contains the same collection queries in machine-readable form. The extractor records explicit start, end, step, scenario, output schema, and a query-config checksum beside every raw export. Container and kube-state queries can legitimately be empty before the shared Prometheus stack scrapes those targets; the extraction pipeline preserves those gaps so validation can reject an incomplete collection instead of treating it as zero usage.
