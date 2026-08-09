# Member 3 platform foundation

This delivery proves the local Capacity AIOps path with an artifact-backed forecasting model before shared platform values are finalized:

```text
demo-workload metrics -> Prometheus query and dashboard panel
                     -> Capacity API recommendation -> Kubernetes deployment and HPA
```

## Included deliverables

- FastAPI Capacity API with frozen-model startup validation, contract-shaped recommendations, health endpoints, and the Capacity API metric catalogue.
- Instrumented demo workload with bounded scenario labels and a repeatable `/work` endpoint.
- Non-root Docker images with version labels and health checks.
- `helm/capacity-api`, which deploys the Capacity API and the demo workload for local validation, including probes, resources, ConfigMap configuration, ServiceAccount, and CPU HPAs.
- PromQL catalogue, recording-rule draft, and the first Grafana dashboard panel set.
- GitLab CI validation, container scanning, and Argo CD project/application definitions.
- A short k6 smoke test that checks the Capacity API and applies controlled normal load to the demo workload.

## Intentionally provisional values

CPU and memory limits, HPA target, HPA bounds, alert threshold, registry image, and Prometheus endpoint are configuration values, not proven production values. They remain provisional until operational load data and shared-cluster constraints are available.

## Local validation

Follow [the local deployment guide](local-deployment.md). The success condition is two available Deployments, two Services, two HPA objects, healthy API responses, and a passing k6 smoke summary.
