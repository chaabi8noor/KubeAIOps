# KubeAIOps

## Member 3 Capacity Management Service

The Member 3 module provides a local, reproducible capacity-management thin slice:

- an instrumented `demo-workload` that exports bounded Prometheus metrics;
- a contract-aligned `capacity-api` recommendation service;
- non-root Docker images, Helm deployment, initial HPAs, PromQL/rules, and a first Grafana dashboard;
- an Argo CD Application skeleton, GitHub Actions validation workflow, and k6 smoke scenario.
- five parameterized k6 load scenarios and a protected pod-recovery test;
- a deterministic raw-to-processed dataset pipeline, validation report, and Prometheus extractor.
- leakage-safe forecasting features, a persistence baseline, a bounded replica policy, and saved baseline evaluation evidence.

Local deployment instructions are in [docs/member-3/local-deployment.md](docs/member-3/local-deployment.md). The platform foundation and known provisional values are documented in [docs/member-3/platform-foundation.md](docs/member-3/platform-foundation.md).

Data-pipeline commands, boundaries, and acceptance checks are in [docs/member-3/capacity-data-pipeline.md](docs/member-3/capacity-data-pipeline.md).

Feature preparation, baseline evaluation, and recommendation-policy guidance are in [docs/member-3/capacity-forecasting-baseline.md](docs/member-3/capacity-forecasting-baseline.md).
