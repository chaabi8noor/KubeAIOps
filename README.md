# KubeAIOps

## Member 3 Capacity AIOps - Week 1-2 vertical skeleton

The Member 3 module provides a local, reproducible capacity-management thin slice:

- an instrumented `demo-workload` that exports bounded Prometheus metrics;
- a contract-aligned `capacity-api` recommendation service;
- non-root Docker images, Helm deployment, initial HPAs, PromQL/rules, and a first Grafana dashboard;
- an Argo CD Application skeleton, GitHub Actions validation workflow, and k6 smoke scenario.

Local deployment instructions are in [docs/member-3/local-deployment.md](docs/member-3/local-deployment.md). The Week 2 scope and known provisional values are documented in [docs/member-3/week-2-vertical-skeleton.md](docs/member-3/week-2-vertical-skeleton.md).
