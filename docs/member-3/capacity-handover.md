# Capacity service handover

This handover lets an independent reviewer deploy, exercise, interpret, and recover the Member 3 capacity stream without verbal guidance.

## Delivery map

| Area | Primary reference |
| --- | --- |
| Service boundaries, contracts, local platform assumptions | [platform-foundation.md](platform-foundation.md) |
| Local Docker, Kind, Helm, HPA, and smoke deployment | [local-deployment.md](local-deployment.md) |
| Dataset collection, schema, cleaning, and feature generation | [capacity-data-pipeline.md](capacity-data-pipeline.md) |
| Baseline, policy, and evaluation | [capacity-forecasting-baseline.md](capacity-forecasting-baseline.md) |
| Frozen model, API behavior, CI, Helm, and GitOps | [primary-model-and-gitops.md](primary-model-and-gitops.md) |
| Scenario execution and recovery evidence | [capacity-validation.md](capacity-validation.md) |
| Diagnosis and corrective actions | [capacity-operations-runbook.md](capacity-operations-runbook.md) |
| Model limitations and versioning | [model card](../../ml/capacity/artifacts/primary-v1/model-card.md) |

## Independent reproduction

From a clean checkout of `member3-capacityHealth`, use the following order:

```bash
make setup-test-env
make test
make config-validate
make helm-lint
make images
make kind-load
make deploy-local
make verify-local
```

Forward both services, run `make load-normal`, then run `make validation-evidence`. The reviewer must locate the Capacity Overview dashboard, call the recommendation endpoint, compare the response with the demo-workload HPA, run `make test-recovery`, and return the cluster to normal with `make verify-local`.

The reviewer should record results in `docs/evidence/member-3/runbook/peer-review.md` using the template below. The documentation is complete enough only when the reviewer can work from repository instructions alone.

```markdown
# Independent review record

- Reviewer:
- Date:
- Branch and commit:
- Prerequisites that were missing or unclear:
- Commands that failed or were ambiguous:
- Dashboard location and interpretation:
- API and HPA observations:
- Recovery result:
- Cleanup result:
- Documentation changes requested:
```

## Secondary review

A second reviewer should perform a lighter check: run `make test`, `make helm-lint`, inspect the validation summary, and confirm that the model card, runbook, evidence map, and final demonstration guide agree on model version, endpoints, and recovery boundaries.

## Acceptance checklist

- [ ] The reviewer deployed both services from the documented commands.
- [ ] The reviewer ran one load scenario and read the generated summary.
- [ ] The reviewer found the dashboard and used a listed PromQL query.
- [ ] The reviewer read a versioned API response and compared it with the HPA state.
- [ ] The reviewer ran protected pod recovery and verified a ready replacement.
- [ ] The reviewer restored normal service and completed the cleanup check.
- [ ] Any documentation gap was corrected and independently retested.

The checklist intentionally remains unmarked until an independent reviewer performs it. This preserves the distinction between prepared handover material and completed peer acceptance.
