# Member 3 Capacity Validation Contract

| Field | Decision |
| --- | --- |
| Status | Proposed for Step 1 review |
| Owner | Member 3 - Capacity AIOps Engineer |
| Reviewers | All members; Member 1 is primary peer-reproduction reviewer |
| Change control | Scenario changes, success criteria, and evidence changes require team review. |

## Test principle

Every capacity scenario must be scripted, parameterized, non-interactive, version-controlled, and safe to run in the selected environment. Each run must preserve its configuration, expected result, actual result, metrics snapshot, Capacity API response, Kubernetes evidence, and conclusion.

Initial performance thresholds are provisional until the normal-load k6 baseline is measured. The safety rules and qualitative acceptance behavior below are fixed now.

## Required scenarios and initial acceptance behavior

| Scenario | Required behavior | Initial command / location |
| --- | --- | --- |
| Normal load | No unnecessary scale-up; normal model result; no false alert. | `make load-normal`, `load-tests/capacity/normal/` |
| Progressive load | Replicas increase before prolonged saturation; API forecast and recommendation change coherently. | `make load-progressive`, `load-tests/capacity/progressive/` |
| Spike load | Workload remains available while the spike is handled; alert behavior follows the agreed duration. | `make load-spike`, `load-tests/capacity/spike/` |
| Sustained load | Capacity remains stable without repeated scale-up/scale-down oscillation. | `make load-sustained`, `load-tests/capacity/sustained/` |
| Pod failure and recovery | A Pod is recreated, traffic continues as far as practical, and recovery is measured. | `make test-recovery`, `load-tests/capacity/recovery/` |
| Capacity API failure | The demo workload remains operational; the API failure becomes observable and recovers cleanly. | `load-tests/capacity/recovery/` |
| Missing metrics | The API returns a controlled unavailable response; it never suggests an unsafe replica count. | API integration test |
| GitOps recovery | A controlled configuration issue is restored through the documented Git and Argo CD recovery path. | `scripts/capacity/` |

The initial target for normal request errors is below 1%. Final error rate, latency, CPU, memory, HPA utilization, alert thresholds, min/max replica values, forecast horizon, and recovery objectives must be derived from recorded k6 evidence and marked provisional until then.

## Fixed safety and consistency criteria

- Every successful recommendation is within configured `MIN_REPLICAS` and `MAX_REPLICAS`.
- Identical valid input produces a stable recommendation.
- A missing or stale metrics input returns `503` and does not return a numeric recommendation.
- Invalid workload input returns `422`; unknown valid workloads return `404`.
- The Capacity API must not become a dependency for the workload to serve traffic.
- Alerts use a duration (initially `for: 2m`) and resolve automatically after recovery.
- Each test starts from a documented known state and includes cleanup or recovery instructions.

## Evidence structure

Store evidence using these stable paths:

```text
docs/evidence/member-3/
├── pipeline/{successful-pipeline,test-results,image-scan,helm-validation}/
├── argocd/{application,sync,healthy-resources,recovery}/
├── api/{health,metrics,normal-response,warning-response,critical-response}/
├── dashboard/{normal-load,progressive-load,spike,scaling,recovery}/
├── model/{evaluation,baseline-comparison,model-version,limitations}/
├── test/{normal,progressive,spike,sustained,pod-failure,recovery}/
└── runbook/{peer-test,final-version}/
```

Each scenario result must include:

1. scenario name, Git commit, date/time in UTC, environment, and input configuration;
2. expected and actual result, including any provisional target used;
3. k6 summary or equivalent workload report;
4. relevant Prometheus query output and dashboard evidence;
5. Capacity API response or controlled error response;
6. HPA/current-replica state and Kubernetes events where applicable;
7. alert evidence and its resolution where applicable;
8. a short conclusion and the path to any follow-up issue.

## Test gates

- Unit, API contract, policy, model-loading, and failure-path tests pass before image packaging.
- Container smoke, Helm lint, and Helm template tests pass before GitOps deployment.
- The normal, progressive, spike, and recovery scenarios run without manual code changes.
- Member 1 can deploy the stream, run one scenario, locate the dashboard, read the API result, observe scaling, and restore normal state using only the runbook.
- Member 2 performs a secondary review of CI/CD and deployment evidence.
