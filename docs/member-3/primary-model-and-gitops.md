# Primary model and GitOps delivery

## Primary forecasting model

`capacity-primary-v1` is an adaptive nearest-neighbor forecast with a bounded persistence fallback. It is trained only from the feature-table training split, uses fixed feature order and scaling metadata, and is packaged with the independent replica policy.

The held-out evaluation contains normal, progressive, spike, sustained, and recovery scenarios. The primary model has an MAE of `0.0273` requests/second, compared with `0.7191` for the persistence baseline. It was therefore selected for the Capacity API.

Reproduce the complete selection and package process from the repository root:

```bash
make model-validate
make package-model
```

The frozen artifacts are stored under `ml/capacity/artifacts/primary-v1/`. The API package under `services/capacity-api/models/primary-v1/` contains the validated model, preprocessor, policy, version record, training metadata, and hash manifest. The model card documents intended use, inputs, outputs, limitations, failure conditions, and versioning.

## Capacity API runtime

The API loads the frozen package during startup and validates its hashes, feature order, model version, policy, and a test prediction. It returns forecast evidence, a bounded recommendation, policy reason, pressure status, and model version. Kubernetes state is never changed by the API.

The Helm ConfigMap controls the configured runtime feature source. These values are safe local defaults and must be replaced with validated telemetry integration before a shared deployment:

- `CAPACITY_SCENARIO`
- `CAPACITY_CURRENT_REQUESTS_PER_SECOND`
- `CAPACITY_REQUEST_RATE_LAG_1`
- `CAPACITY_REQUEST_RATE_ROLLING_MEAN`
- `CAPACITY_CPU_UTILIZATION`
- `CAPACITY_P95_LATENCY_SECONDS`
- `CAPACITY_ERROR_RATIO`
- `CAPACITY_CURRENT_REPLICAS`

Invalid features return a controlled `422` response. An unavailable source returns a controlled `503` response. Prediction and source failures are recorded in Prometheus with bounded labels.

## Container and Helm package

Build and verify both images locally:

```bash
make images
docker run --rm -p 8000:8000 kubeaiops/capacity-api:dev
curl -s http://127.0.0.1:8000/health/ready
```

The Capacity API image runs as a non-root user, includes only its application and frozen model package, exposes health checks, and has a read-only-root-filesystem-compatible deployment. The Helm chart includes Deployment, Service, ServiceAccount, ConfigMap, HPA, PodDisruptionBudget, optional ServiceMonitor, and optional PrometheusRule.

Validate the chart lifecycle after the local images are available in Kind:

```bash
make helm-lint
make helm-template
make kind-load
make deploy-local
make verify-local
helm upgrade capacity-api helm/capacity-api --namespace kubeaiops --values helm/capacity-api/values-local.yaml --wait
helm rollback capacity-api 1 --namespace kubeaiops
helm uninstall capacity-api --namespace kubeaiops
```

The `CapacityRecommendationGapHigh` alert only fires after the configured sustained duration. Its action is to inspect workload demand, HPA state, resource limits, and API evidence before any operator intervention.

## GitLab CI and GitOps

`.gitlab-ci.yml` validates Python and configuration files, runs API/model/policy tests, freezes a reproducible model evaluation, lints and renders Helm, builds and scans images, runs a container smoke test, and validates every k6 script. Image tags use the GitLab commit short SHA and are pushed to the project registry.

The Argo CD project and application are versioned under `gitops/`. After Argo CD is installed and has read access to the GitLab repository, apply and verify the managed deployment:

```bash
kubectl apply -f gitops/projects/kubeaiops.yaml
kubectl apply -f gitops/applications/capacity-api.yaml
argocd app sync capacity-api
argocd app wait capacity-api --health --sync --timeout 300
argocd app get capacity-api
```

The application enables pruning and self-healing. To verify drift correction, make a safe temporary change to an owned resource, inspect the `OutOfSync` state, and synchronize the application. To recover a release, select a known-good revision from `argocd app history capacity-api`, run `argocd app rollback capacity-api <revision>`, then wait for healthy synchronized status.
