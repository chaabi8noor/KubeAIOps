# Capacity operations runbook

Use this sequence for every incident: establish the current deployment and HPA state, inspect the Capacity API health and recommendation, check the listed PromQL query, apply the smallest corrective action, then repeat the original check to confirm recovery. Do not treat an empty Prometheus result as zero traffic.

## Fast checks

```bash
kubectl -n kubeaiops get deployment,pods,service,hpa -o wide
kubectl -n kubeaiops get events --sort-by=.lastTimestamp
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://127.0.0.1:8000/api/v1/capacity/demo-workload/recommendation | python3 -m json.tool
```

Use the Capacity Overview dashboard with the PromQL catalogue in [monitoring/capacity/promql/queries.md](../../monitoring/capacity/promql/queries.md). The dashboard panels and queries are diagnostic evidence; they do not authorize an automatic production change.

| Symptom | Checks and query | Expected API result | Likely cause | Corrective action and verification |
| --- | --- | --- | --- | --- |
| No workload metrics | Confirm ServiceMonitor or scrape configuration and inspect `sum by (workload) (rate(kubeaiops_workload_requests_total{namespace="kubeaiops",service="demo-workload"}[5m]))` | A valid recommendation may use configured fallback values; no fabricated telemetry | Target not scraped, wrong labels, or instrumentation unavailable | Fix the scrape target or labels. Wait two scrape intervals and confirm a non-empty series. |
| Forecast unavailable | Check API logs and `kubeaiops_capacity_api_requests_total`; call the recommendation endpoint | Controlled `503` or `422`, never a malformed success | Invalid feature, missing source, corrupted or mismatched artifact | Correct the feature source or restore the validated model package; restart the API and confirm a versioned `200` response. |
| Capacity API unhealthy | `kubectl describe pod`, readiness endpoint, API request metric | Readiness returns `200` only after model validation | Probe failure, image mismatch, configuration error | Inspect the previous container log, restore the known-good Helm values or image, and wait for deployment availability. |
| No scaling under demand | Inspect HPA `currentMetrics`, events, CPU query, and resource requests | Recommendation can be `scale_up`; it does not scale pods itself | Metrics Server unavailable, HPA target not crossed, request/limit mismatch | Repair the metrics path or values, then observe HPA desired replicas during the same load scenario. |
| Excessive scaling or oscillation | Compare HPA events, replica history, request rate, and `kubeaiops_capacity_recommendation_gap` | Bounded recommendation; action reflects observed forecast | Aggressive HPA bounds, unstable demand, too-short stabilization | Tune only through reviewed Helm values; rerun sustained load and confirm a stable replica count. |
| Pod restart or replacement | Inspect pod restart count, deployment status, and events | API remains healthy if enough API replicas are ready | Crash, eviction, probe failure, node pressure | Preserve events and logs, replace the failed pod through the Deployment, and confirm ready replica count returns. |
| High latency | Query workload p95: `histogram_quantile(0.95, sum by (le) (rate(kubeaiops_workload_request_duration_seconds_bucket{namespace="kubeaiops",service="demo-workload"}[5m])))` | Recommendation exposes current and forecast pressure evidence | CPU saturation, expensive workload parameters, insufficient replicas | Reduce unsafe test parameters or increase capacity through reviewed values; repeat the request and compare p95. |
| High errors | Query `sum(rate(kubeaiops_workload_errors_total{namespace="kubeaiops",service="demo-workload"}[5m])) / clamp_min(sum(rate(kubeaiops_workload_requests_total{namespace="kubeaiops",service="demo-workload"}[5m])), 1)` | API error must be explicit (`422` or `503`) rather than hidden | Application fault, bad request, dependency issue | Inspect response and logs, correct the underlying fault, then confirm the error ratio returns to baseline. |
| Recommendation differs from HPA | Compare recommendation fields with `kubectl get hpa demo-workload` and the gap metric | A bounded, versioned recommendation; no Kubernetes mutation | Separate decision mechanisms, HPA delay, CPU metric differs from forecast input | Explain the input difference, HPA stabilization, or policy bounds. Change neither system until the discrepancy is understood. |
| Argo CD out of sync | `argocd app get capacity-api`, application history, owned-resource diff | API behavior is independent of Argo status | Drift, repository revision, invalid values | Sync or roll back a known-good revision, then wait for `Healthy` and `Synced`. If Argo CD is absent, record the scenario as blocked. |
| Failed image deployment | Inspect Deployment events, image digest, and CI build/scan output | API fails readiness rather than serving an unvalidated model | Missing image, registry authorization, incompatible artifact | Restore the last verified image and values; wait for readiness and rerun the health endpoint. |

## Controlled recovery boundaries

Use `make test-recovery` only on a local Kind cluster. It deletes one demo-workload pod while k6 continues traffic and waits for a distinct ready replacement. Use `make test-api-resilience` only on Kind; it temporarily scales the Capacity API to zero, confirms the workload remains healthy, restores the original replica count, and records the outcome. Both commands have context guards. For GitOps recovery, use the procedure in [capacity-validation.md](capacity-validation.md#gitops-recovery-procedure) after Argo CD is installed and authorized.
