# Member 3 local deployment guide

## Prerequisites

- Docker Desktop running
- Kind cluster named `kubeaiops`
- kubectl context `kind-kubeaiops`
- Helm and either a local k6 binary or Docker Desktop (the scenario wrapper uses a pinned k6 container when the binary is unavailable)

## Build and deploy

From the repository root, run:

```bash
sh scripts/capacity/install-metrics-server.sh
make setup-test-env
make test
make helm-lint
make kind-load
make deploy-local
make verify-local
```

The local values file intentionally uses the `dev` image tag and `imagePullPolicy: Never`; the Kind image-load step is therefore required before installation.

## Smoke test

In one terminal, forward both services:

```bash
kubectl -n kubeaiops port-forward service/capacity-api 8000:8000
kubectl -n kubeaiops port-forward service/demo-workload 8001:8000
```

In a second terminal, run:

```bash
make k6-smoke
```

Expected result: k6 reports zero failed requests, and `docs/evidence/member-3/k6-smoke-summary.json` is produced locally. The summary is ignored by Git because it is run-specific evidence. The Capacity API may return `hold`, `scale_up`, or `scale_down`; each is valid when the versioned response is well formed.

## Manual endpoint checks

```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
curl -s http://127.0.0.1:8000/api/v1/capacity/demo-workload/recommendation | python3 -m json.tool
curl -s http://127.0.0.1:8001/metrics | grep kubeaiops_workload
```

## HPA note

The chart creates CPU-based HPA objects for the Capacity API and demo workload. The local helper installs the Metrics Server version compatible with Kubernetes 1.31+ and adds Kind's local-only insecure kubelet TLS option. Do not use this flag in a shared or production cluster; there, use the platform-approved Metrics Server configuration.

## Remove local resources

```bash
helm uninstall capacity-api --namespace kubeaiops
```
