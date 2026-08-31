# Integration dependency register

This register distinguishes completed Member 3 work from activities that require another contributor or a platform owner. A paused item is not a failed item: it has a concrete prerequisite and a defined resume action.

## Completed Member 3 delivery

The `member3-capacityHealth` branch contains the Capacity API, demo workload, frozen primary model, Docker images, Helm chart, HPA and disruption budget, monitoring definitions, CI configuration, GitOps definitions, load scenarios, controlled resilience tests, operational runbook, handover material, and demonstration guide.

The local validation evidence records successful normal, progressive, spike, sustained, pod-recovery, and Capacity API resilience checks. See [validation evidence](../evidence/member-3/validation/README.md).

## Paused integration items

| Item | Current evidence | Pause condition | Resume action | Owner |
| --- | --- | --- | --- | --- |
| Canonical shared integration branch | `member3-capacityHealth` has no common Git ancestor with the GitLab integration history. Member 1 and Member 2 share the GitLab `main` base, but Member 3 must still be brought in through reviewed commits or an agreed migration. | A normal merge of the Member 3 delivery would combine unrelated histories and obscure ownership or conflicts. | The project owner selects a canonical integration branch based on `gitlab/main`, then brings in each member stream through reviewed commits or merge requests. | Project owner and all members |
| Shared Prometheus and Grafana validation | Member 1 completed the anomaly API package, Helm chart, ServiceMonitor, Prometheus rule, dashboard, and GitLab image pipeline on `804aef0`. The Member 3 local application consumes that chart with a preloaded image. | Dashboard and alert evidence still needs a dedicated cluster with a Prometheus Operator and Grafana. | Install the monitoring stack, synchronize the local applications, re-run the Capacity API load scenarios, and capture dashboard and alert evidence. | Member 3 |
| Release-risk platform integration | Member 2 completed its chart, validation scenario, and runbook on `95e5aef`. The Member 3 local application corrects the upstream Application's branch selection and pins the immutable `95e5aef` image tag without modifying the Member 2 branch. | Deployment and metrics evidence still needs the dedicated cluster. | Build or pull the pinned image, synchronize the local application, run the supplied healthy and degraded release scenario, and record the result. | Member 3 |
| Live GitOps synchronization and recovery | The Capacity Argo CD Project, staging Application, and local Applications for capacity, anomaly, and release-risk are committed and configuration-tested. | Live synchronization and rollback cannot be claimed until a functioning dedicated Kind cluster with Argo CD and monitoring is available. | Build and load the local images, install Argo CD and monitoring in the dedicated cluster, apply the Project and local Applications, capture synchronized health, introduce controlled drift, and execute the documented recovery. | Member 3 |
| Independent reproduction review | The handover instructions and review template are committed. | A Member 1 primary review and Member 2 secondary review must be performed by those members, not simulated. | Each reviewer follows [capacity-handover.md](capacity-handover.md), records their result, and any documentation gap is corrected and retested. | Members 1 and 2 |
| Final group demonstration | The Member 3 demonstration guide is committed. | It needs the canonical integration branch, shared monitoring, and the completed cross-stream deployment. | Rehearse against the integrated environment using [capacity-demonstration.md](capacity-demonstration.md), then freeze the group evidence. | All members |

## Handoff checklist when a prerequisite arrives

1. Fetch the contributor branch and inspect its commit, tests, and deployment manifest before merging.
2. Verify the integration contract remains compatible; do not adapt another member's service silently.
3. Add only the smallest required adapter or configuration on the owning stream, with a test-first change when production behavior changes.
4. Run the Member 3 test suite, Helm validation, and relevant end-to-end scenario again.
5. Record the new evidence with the integration commit and update this register from `Paused` to `Completed`.

## Guardrails

- Do not force-push or merge unrelated histories into a member delivery branch.
- Do not mark dashboard, alert, GitOps, peer-review, or group-demo evidence as completed until the required party performs it.
- Do not commit credentials, cluster tokens, or screenshots containing sensitive data.
