# Capacity management demonstration

Target duration: ten minutes. Use an isolated local or shared demonstration environment with no production workload. Open the Capacity Overview dashboard, terminal with Kubernetes status, and a terminal with the Capacity API endpoint before starting.

## Preparation

1. Show the passing test, Helm render, image, and validation-evidence outputs.
2. Show `kubectl -n kubeaiops get deployment,pods,hpa` with both services healthy.
3. Call the recommendation endpoint and point out `model_version`, forecast evidence, action, and bounded replica recommendation.
4. Confirm there is no active alert and that the current HPA count is visible.

## Progressive demand and spike

1. Run `make load-progressive`; narrate traffic, CPU, forecast evidence, recommendation, and HPA desired replicas as the stages change.
2. Run `make load-spike`; identify the baseline, spike, and recovery segments in the generated report.
3. Compare recommendation replicas with current and desired HPA replicas. Explain any difference through the independent policy and HPA inputs or stabilization behavior; do not present them as a single controller.
4. Review p95 latency, error ratio, request rate, and any alert state from the dashboard.

## Recovery

1. Run `make test-recovery` while the workload is receiving traffic.
2. Show the deleted pod, the new ready pod, the event sequence, and the recovery result.
3. Run `make test-api-resilience` and show that Capacity API unavailability is observable while the demo workload remains available, followed by API recovery.
4. Generate `make validation-evidence` and open the final summary.

## GitOps segment

Only demonstrate this portion when Argo CD is installed and authorized for the GitLab repository. Show `argocd app get capacity-api`, a controlled owned-resource drift, the out-of-sync state, the documented rollback or synchronization, and the final healthy synchronized state. If Argo CD is unavailable, state that the repository definitions and recovery procedure are ready, but do not present this as executed evidence.

## Close

Show the generated validation summary, the final API response, recovered Kubernetes resources, the relevant runbook entry, the model card, and the evidence locations. Conclude with current limitations: local configuration uses validated fixture-style inputs, the Capacity API does not mutate Kubernetes, and shared-cluster telemetry and Argo CD validation require platform integration.
