# GitOps recovery status

Checked on 2026-08-14 in context `kind-kubeaiops`.

## Result

**Blocked — not executed.** The local cluster does not contain the `applications.argoproj.io` CustomResourceDefinition, so Argo CD is not installed there. A live synchronization, drift observation, or rollback would therefore be a false claim.

The versioned GitOps inputs are ready for a cluster that has Argo CD and authorized GitLab access:

- `gitops/projects/kubeaiops.yaml`
- `gitops/applications/capacity-api.yaml`
- `helm/capacity-api/values-staging.yaml`
- [GitOps recovery procedure](../../../member-3/primary-model-and-gitops.md#gitops-recovery-procedure)

Once the platform owner installs and authorizes Argo CD, apply the Project and Application, synchronize `capacity-api`, introduce a controlled owned-resource drift, save the `OutOfSync` status, then recover a known-good revision and retain the final `Healthy` and `Synced` status.
