# Capacity validation evidence

The local Kind validation campaign was executed on 2026-08-14 against the `capacity-primary-v1` runtime. The compact results are in [validation-summary.md](validation-summary.md), generated from the ignored raw k6 reports so that the reviewed result remains traceable without committing bulky run output.

| Evidence | Result | Notes |
| --- | --- | --- |
| Normal, progressive, spike, sustained load | Passed | Zero failed-request rate and zero failed checks across all four scenarios. The spike p95 was 283.37 ms, within the 1000 ms acceptance threshold. |
| Pod failure | Passed | Continuous traffic completed while a distinct demo-workload replacement reached ready state. The replacement identifiers and timestamps are retained in the summary JSON. |
| Capacity API resilience | Passed | The API had no ready service endpoint during the controlled disruption, the demo workload remained available, and the API was healthy after restoration. See [capacity-api-resilience.json](capacity-api-resilience.json). |
| Final Kubernetes state | Passed | Both Deployments were available, both HPAs were present, and the Capacity API PDB allowed no voluntary disruptions below one available pod. See [kubernetes-state.md](kubernetes-state.md). |
| Dashboard and alert capture | Not available locally | Prometheus and Grafana were not deployed as part of this Kind environment, so no dashboard or alert evidence is claimed. |
| GitOps recovery | Blocked | The versioned local Argo CD Application is ready, but a dedicated Kind environment could not be created during the latest check because Docker Desktop was unavailable. See [GitOps recovery status](../gitops/recovery-status.md). |

The test records use the local `kind-kubeaiops` context. They demonstrate reproducible development validation; they are not a substitute for a shared-cluster capacity assessment with production telemetry.
