# Integration dependency register

This register distinguishes completed Member 3 work from activities that require another contributor or a platform owner. A paused item is not a failed item: it has a concrete prerequisite and a defined resume action.

## Completed Member 3 delivery

The `member3-capacityHealth` branch contains the Capacity API, demo workload, frozen primary model, Docker images, Helm chart, HPA and disruption budget, monitoring definitions, CI configuration, GitOps definitions, load scenarios, controlled resilience tests, operational runbook, handover material, and demonstration guide.

The local validation evidence records successful normal, progressive, spike, sustained, pod-recovery, and Capacity API resilience checks. See [validation evidence](../evidence/member-3/validation/README.md).

## Paused integration items

| Item | Current evidence | Pause condition | Resume action | Owner |
| --- | --- | --- | --- | --- |
| Canonical shared integration branch | `member3-capacityHealth` has no common Git ancestor with the GitLab integration history. Member 1 and Member 2 share the GitLab `main` base, but Member 3 must still be brought in through reviewed commits or an agreed migration. | A normal merge of the Member 3 delivery would combine unrelated histories and obscure ownership or conflicts. | The project owner selects a canonical integration branch based on `gitlab/main`, then brings in each member stream through reviewed commits or merge requests. | Project owner and all members |
| Shared Prometheus and Grafana validation | Member 1 added a ServiceMonitor, Prometheus rule, dashboard, Helm chart, and Argo CD Application on `d43d409`. The Helm chart deploys default NGINX while the raw deployment expects a local `anomaly-api:v1` image, so the application and its telemetry are not yet a coherent shared deployment. | Capacity dashboard and alert evidence cannot be produced honestly from an inconsistent upstream application package. | Member 1 aligns the image, port, probes, labels, metrics endpoint, and published image; then provide a successful scrape verification. Re-run the Capacity API load scenarios and capture dashboard and alert evidence. | Member 1 |
| Release-risk platform integration | Member 2 added a Helm chart, Argo CD Application, dashboard, and alert configuration on `97bed23`. The Application targets `main` even though the chart exists only on `member2/containerize-and-deploy`; its Helm values also request `latest` while CI publishes commit-SHA tags. | Argo CD cannot reliably find or pull the intended Release Risk image and chart. | Member 2 aligns the Application revision with the canonical branch, publishes the selected image tag, creates the referenced Argo CD project or uses the approved project, and captures deployment and metrics validation. | Member 2 |
| Live GitOps synchronization and recovery | The Capacity Argo CD Project and staging Application definitions are committed. A separate `capacity-api-kind` Application now provides a versioned local Kind rehearsal using preloaded images. | Live synchronization and rollback cannot be claimed until a functioning dedicated Kind cluster with Argo CD is available. | Build and load the local images, install Argo CD in the dedicated cluster, apply the Project and Kind Application, capture synchronized health, introduce controlled drift, and execute the documented recovery. | Member 3 |
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
