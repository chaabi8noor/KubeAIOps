# Kubernetes state after validation

Observed on 2026-08-14 in context `kind-kubeaiops`, namespace `kubeaiops`.

| Resource | Observed state |
| --- | --- |
| `deployment/capacity-api` | Available: 1 of 1; image `kubeaiops/capacity-api:dev` |
| `deployment/demo-workload` | Available: 1 of 1; image `kubeaiops/demo-workload:dev` |
| `hpa/capacity-api` | CPU target 70%, range 1–3, current 1 replica |
| `hpa/demo-workload` | CPU target 70%, range 1–3, current 1 replica |
| `pdb/capacity-api` | Minimum available 1; allowed voluntary disruptions 0 |

The Capacity API health endpoint returned `{"status":"ok","version":"0.2.0"}` after the resilience restoration. The final normal recommendation response is retained under [../api/normal-recommendation.json](../api/normal-recommendation.json).
