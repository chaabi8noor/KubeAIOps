# Integration dependency register

This register distinguishes completed Member 3 work from activities that require another contributor or a platform owner. A paused item is not a failed item: it has a concrete prerequisite and a defined resume action.

## Completed Member 3 delivery

The `member3-capacityHealth` branch contains the Capacity API, demo workload, frozen primary model, Docker images, Helm chart, HPA and disruption budget, monitoring definitions, CI configuration, GitOps definitions, load scenarios, controlled resilience tests, operational runbook, handover material, and demonstration guide.

The local validation evidence records successful normal, progressive, spike, sustained, pod-recovery, and Capacity API resilience checks. See [validation evidence](../evidence/member-3/validation/README.md).

## Paused integration items

| Item | Current evidence | Pause condition | Resume action | Owner |
| --- | --- | --- | --- | --- |
| Canonical shared integration branch | `member3-capacityHealth` has no common Git ancestor with `gitlab/main`, `gitlab/member1-infrastructure`, or `gitlab/member2/containerize-and-deploy`. | A normal merge would combine unrelated histories and obscure ownership or conflicts. | The project owner creates or selects a canonical integration branch based on `gitlab/main`; then bring each member stream in through reviewed commits or merge requests. | Project owner and all members |
| Shared Prometheus and Grafana validation | Member 1 has committed a stress deployment and metric-export script, but no shared Prometheus deployment, ServiceMonitor/scrape configuration, or Grafana dashboard export is committed. | Capacity dashboard and alert screenshots cannot be produced honestly without a running shared observability stack. | Member 1 commits the shared monitoring manifests, dashboard import path, and scrape verification. Re-run the Capacity API load scenarios and capture dashboard and alert evidence. | Member 1 |
| Release-risk platform integration | Member 2 has committed the release-risk API, model, and Dockerfile, while its Helm and Argo CD directories are placeholders and its branch remains separate from the canonical project history. | Cross-stream deployment and the group demonstration cannot use an unintegrated release service. | Member 2 completes tests, deployment manifests, metrics validation, and documented configuration; then integrate through the canonical branch. | Member 2 |
| Live GitOps synchronization and recovery | The Capacity Argo CD Project and Application definitions are committed, but the local Kind cluster has no `applications.argoproj.io` CRD. | Argo CD is not installed or authorized to read the GitLab project, so live synchronization and rollback cannot be claimed. | Platform owner installs and authorizes Argo CD; apply the versioned Project and Application, capture synchronized health, introduce controlled drift, and execute the documented recovery. | Platform owner |
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
