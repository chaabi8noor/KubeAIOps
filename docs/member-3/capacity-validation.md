# Capacity validation campaign

This campaign verifies the Capacity API, demo workload, load scenarios, and controlled recovery behavior. It records measured output rather than treating a deployed manifest as proof of service health.

## Preconditions

- Docker Desktop is running and the `kind-kubeaiops` context is selected.
- The Helm release is available: `make verify-local`.
- Forward the services in separate terminals. If ports `8000` and `8001` are already used, replace them consistently in the commands below.

```bash
kubectl -n kubeaiops port-forward service/capacity-api 8000:8000
kubectl -n kubeaiops port-forward service/demo-workload 8001:8000
```

The scenario runner uses a local `k6` binary when present. Otherwise it falls back to the pinned `grafana/k6:0.57.0` image and translates loopback endpoints to Docker Desktop's host gateway.

## Scenario matrix

| Scenario | Command | Expected result | Evidence retained |
| --- | --- | --- | --- |
| Normal load | `make load-normal` | Bounded request rate, zero failed-request rate, p95 below 1000 ms | k6 summary and stage record |
| Progressive load | `make load-progressive` | Each configured rate stage completes while the recommendation endpoint stays reachable | k6 summary, stage record, API sample, HPA snapshot |
| Sudden spike | `make load-spike` | Baseline, spike, and recovery stages complete without failed requests | k6 summary, API sample, HPA snapshot |
| Sustained load | `make load-sustained` | High rate remains healthy for the configured duration without oscillation evidence | k6 summary, HPA events, dashboard capture |
| Pod failure | `make test-recovery` | One demo-workload pod is replaced while traffic continues | replacement record, k6 summary, events |
| Capacity API disruption | `make test-api-resilience` | The demo workload remains reachable; API unavailability is observable; API returns healthy after restoration | resilience JSON, pod snapshot, events |
| GitOps recovery | See [GitOps procedure](primary-model-and-gitops.md#gitops-recovery-procedure) | Controlled drift is observed and a known-good revision returns to healthy synchronized state | Argo CD history, application status, Kubernetes resources |

The pod and API-disruption commands are protected by Kind-context checks and restore the original replica count even when the test fails. Do not run them on a shared cluster without the platform owner's approval.

## Execution and assessment

Run the non-disruptive traffic scenarios:

```bash
make capacity-validation
```

Run the controlled resilience scenarios separately:

```bash
make test-recovery
make test-api-resilience
```

Then convert the ignored k6 outputs into the committed, compact evidence record:

```bash
make validation-evidence
```

`docs/evidence/member-3/validation/validation-summary.json` is the machine-readable result. Its Markdown companion is intended for review. A `not-run` or `incomplete` status is an evidence gap, not a passing result.

## Kubernetes and API evidence

Capture this before and after every scenario. Store outputs under `docs/evidence/member-3/` only after removing any sensitive values.

```bash
kubectl -n kubeaiops get deployment,pods,service,hpa -o wide
kubectl -n kubeaiops get events --sort-by=.lastTimestamp
curl -fsS http://127.0.0.1:8000/api/v1/capacity/demo-workload/recommendation | python3 -m json.tool
curl -fsS http://127.0.0.1:8000/metrics | grep kubeaiops_capacity
```

Compare the recommendation's `replicas` and `action` with the current and desired HPA replica counts. They are independent controls: the API supplies a bounded recommendation and never mutates Kubernetes; the HPA reacts to CPU utilization. A difference must be explained through demand, HPA stabilization, resource usage, or configuration rather than silently treated as an error.

## GitOps recovery procedure

The repository includes the Argo CD Application and Project definitions, but the local Kind cluster must already have Argo CD installed and authorized to read GitLab before a live recovery can be run. With that precondition met:

```bash
kubectl apply -f gitops/projects/kubeaiops.yaml
kubectl apply -f gitops/applications/capacity-api.yaml
argocd app sync capacity-api
argocd app wait capacity-api --health --sync --timeout 300
argocd app history capacity-api
```

Introduce a small, owned change to a generated resource only in an isolated environment. Confirm `OutOfSync`, restore a known-good revision with `argocd app rollback capacity-api <revision>`, then wait for both healthy and synchronized status. Save the application status before the change, the drift observation, the selected revision, and the final resource snapshot. If the Argo CD CRD or controller is absent, record the scenario as blocked; do not claim GitOps recovery passed.
