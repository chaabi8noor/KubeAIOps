# Member 3 Deployment and GitOps Contract

| Field | Decision |
| --- | --- |
| Status | Proposed for Step 1 review |
| Owner | Member 3 - Capacity AIOps Engineer |
| Reviewers | Member 1 for Kubernetes conventions; Member 2 for CI/CD and Argo CD |
| Change control | Names and paths below are stable interfaces and require a reviewed merge request to change. |

## Stable resource identity

| Resource | Stable value |
| --- | --- |
| Namespace | `kubeaiops` |
| Kubernetes Deployment | `capacity-api` |
| Kubernetes Service | `capacity-api` |
| ServiceAccount | `capacity-api` |
| ConfigMap | `capacity-api-config` |
| Helm release and chart directory | `capacity-api`, `helm/capacity-api/` |
| Argo CD Application | `capacity-api` |
| Argo CD manifest | `gitops/applications/capacity-api.yaml` |
| PrometheusRule | `capacity-api-rules` |
| Grafana folder | `KubeAIOps / Capacity` |
| Grafana dashboard UID | `kubeaiops-capacity` |
| Capacity service port name | `http` |

All resources must use the common `app.kubernetes.io/*` labels defined in [the metrics contract](metrics-contract.md). Selectors must use stable labels, never generated Pod names.

## Image and versioning

The image name is `capacity-api`. Its registry path must use this form:

```text
<registry>/<group>/<project>/capacity-api:<tag>
```

Examples, pending final GitLab registry confirmation:

```text
registry.gitlab.com/kubeaiops/platform/capacity-api:v0.1.0
registry.gitlab.com/kubeaiops/platform/capacity-api:sha-a83f921
```

Use a semantic version tag for a human release and an immutable commit-SHA tag for every deployed image. `latest` is forbidden in Helm values, Argo CD manifests, deployment commands, and evidence because it prevents reliable rollback.

The final registry host, group, project, and authentication mechanism remain provisional until Member 2 confirms the shared CI/CD foundation; the image name and tag rules are frozen now.

## Helm package

The chart has this required layout:

```text
helm/capacity-api/
├── Chart.yaml
├── values.yaml
├── values-local.yaml
├── values-staging.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    ├── serviceaccount.yaml
    ├── configmap.yaml
    ├── hpa.yaml
    ├── servicemonitor.yaml
    ├── prometheusrule.yaml
    └── tests/
```

The rendered deployment must include:

- explicit CPU and memory requests and limits;
- liveness probe at `/health/live` and readiness probe at `/health/ready`;
- the `capacity-api` ServiceAccount;
- non-root security context required by the security contract;
- ConfigMap references for non-sensitive configuration;
- an HPA that observes the deployment but does not consume an API action directly;
- a ServiceMonitor placeholder or active resource following the shared Prometheus convention.

CPU and memory quantities, HPA targets, HPA replica limits, environment quota, and ingress/TLS rules are deliberately provisional until they are supported by load tests and the shared cluster constraints.

## Configuration boundary

| ConfigMap key (committed) | Secret only (never committed) |
| --- | --- |
| `PROMETHEUS_URL` | Prometheus authentication token |
| `FORECAST_HORIZON_SECONDS` | Registry credentials |
| `MIN_REPLICAS` | External-service credentials |
| `MAX_REPLICAS` | Any sensitive endpoint credential |
| `MODEL_PATH` | |
| `LOG_LEVEL` | |

Do not place secrets, passwords, tokens, or registry credentials in `values.yaml`, GitOps manifests, ConfigMaps, test reports, or screenshots.

## Argo CD policy and recovery

The required initial Application policy is:

```yaml
spec:
  project: kubeaiops
  destination:
    namespace: kubeaiops
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

The final destination cluster and Argo CD project permissions remain provisional until Member 2 confirms them. The application name, namespace, path, and automated reconciliation behavior are the agreed default.

Recovery follows this auditable path:

```text
Git revert -> pipeline validation -> merge -> Argo CD detects change -> sync -> health verification
```

Do not leave manual cluster changes as the desired state. A manual change used to demonstrate drift must be reconciled back to Git and captured in `docs/evidence/member-3/argocd/recovery/`.

## Deployment acceptance check

- [ ] `helm lint` and `helm template` succeed for the default and local values.
- [ ] Deployment, Service, ServiceAccount, ConfigMap, HPA, and monitoring resources render with the stable names above.
- [ ] Probes, resource boundaries, and least-privilege settings are present.
- [ ] The Argo CD Application reports the expected repository path, namespace, image tag, sync, and health status.
- [ ] A Git-based rollback and recovery result is documented.
