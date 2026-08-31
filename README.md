# KubeAIOps

## Member 3 Capacity Management Service

The Member 3 module provides a local, reproducible capacity-management thin slice:

- an instrumented `demo-workload` that exports bounded Prometheus metrics;
- a contract-aligned `capacity-api` recommendation service;
- non-root Docker images, Helm deployment, initial HPAs, PromQL/rules, and a first Grafana dashboard;
- a GitLab CI pipeline, Argo CD project/application definitions, and k6 validation scripts.
- versioned local Argo CD applications for the capacity, infrastructure-anomaly, and release-risk services.
- five parameterized k6 load scenarios and a protected pod-recovery test;
- a deterministic raw-to-processed dataset pipeline, validation report, and Prometheus extractor.
- leakage-safe forecasting features, a persistence baseline, a bounded replica policy, and saved baseline evaluation evidence.
- a frozen primary forecast model, model card, artifact-backed API, image scan policy, and GitOps recovery procedure.
- a complete validation campaign, protected resilience checks, operational runbook, peer-reproduction handover, and final demonstration guide.

Local deployment instructions are in [docs/member-3/local-deployment.md](docs/member-3/local-deployment.md). The platform foundation and known provisional values are documented in [docs/member-3/platform-foundation.md](docs/member-3/platform-foundation.md).

Data-pipeline commands, boundaries, and acceptance checks are in [docs/member-3/capacity-data-pipeline.md](docs/member-3/capacity-data-pipeline.md).

Feature preparation, baseline evaluation, and recommendation-policy guidance are in [docs/member-3/capacity-forecasting-baseline.md](docs/member-3/capacity-forecasting-baseline.md).

Primary-model selection, API runtime, CI, Helm, alerting, and GitOps guidance are in [docs/member-3/primary-model-and-gitops.md](docs/member-3/primary-model-and-gitops.md).

Validation procedures and evidence expectations are in [docs/member-3/capacity-validation.md](docs/member-3/capacity-validation.md). Operations, handover, and demonstration material is in [docs/member-3/capacity-operations-runbook.md](docs/member-3/capacity-operations-runbook.md), [docs/member-3/capacity-handover.md](docs/member-3/capacity-handover.md), and [docs/member-3/capacity-demonstration.md](docs/member-3/capacity-demonstration.md).

Cross-stream dependencies and the exact conditions for resuming paused integration work are tracked in [docs/member-3/integration-dependency-register.md](docs/member-3/integration-dependency-register.md).
