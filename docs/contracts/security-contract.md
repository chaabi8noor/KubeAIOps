# Member 3 Security Contract

| Field | Decision |
| --- | --- |
| Status | Proposed for Step 1 review |
| Owner | Member 3 - Capacity AIOps Engineer |
| Primary reviewer | Member 2 - Release AIOps Engineer |
| Change control | Security exceptions are time-limited and must be reviewed. |

## Scope

This policy governs the Capacity API image, its Helm resources, CI artifacts, and the capacity module's configuration. Member 2 may provide shared scanners, but Member 3 owns interpreting and fixing findings in the Capacity API stream.

## Image and runtime baseline

The Capacity API image must:

- use pinned Python dependencies and a reproducible dependency-installation command;
- run as a dedicated non-root user with UID `10001`;
- include only required application, dependency, and model files;
- define an explicit startup command and health check;
- include a `.dockerignore` that excludes virtual environments, test output, local models not needed at runtime, credentials, and VCS metadata;
- never include a private key, token, password, or real production dataset in an image layer.

The Helm deployment must set at least:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
```

If the runtime needs temporary writable storage, it must use a narrowly scoped `emptyDir` mount. Privileged mode, host networking, host PID/IPC namespaces, and `hostPath` mounts are prohibited.

## Secrets and configuration

- Do not commit secrets to Git, including in `.env`, Helm values, GitLab CI variables, evidence, fixtures, or notebooks.
- Non-sensitive settings belong in the `capacity-api-config` ConfigMap as defined by the deployment contract.
- Sensitive values are injected by the approved platform mechanism and referenced by name only in manifests.
- The Capacity API must not log authorization headers, connection strings, tokens, complete Prometheus responses, or environment dumps.
- Gitleaks findings are investigated before merge. A verified secret fails the pipeline and is remediated through revocation and repository cleanup, not by simply suppressing the finding.

## CI security gates

| Gate | Required policy |
| --- | --- |
| Gitleaks | Fail for a verified secret. |
| Trivy CRITICAL | Fail the pipeline. |
| Trivy HIGH | Fail unless an approved, unexpired exception exists. |
| Container smoke test | Must pass using the built image. |
| Helm render/lint | Must pass before deploy packaging. |
| Scan reports | Publish as CI artifacts for 14-30 days. |

The precise shared Trivy configuration, Gitleaks configuration file, and artifact-retention period remain provisional until Member 2 publishes the shared CI template. These quality gates are not provisional.

## Vulnerability exception record

An allowed HIGH finding requires a version-controlled exception record containing all of the following:

```text
CVE:
Affected dependency:
Why it cannot currently be fixed:
Risk:
Compensating control:
Expiration date:
Owner:
```

Exceptions must expire and be reviewed; they cannot waive CRITICAL findings or secret exposure.

## Network and access controls

- Use the `capacity-api` ServiceAccount with only the permissions the service actually needs. The API is recommendation-only and should not need permission to scale workloads.
- Add a NetworkPolicy when the shared cluster supports it. The policy should permit only necessary inbound Prometheus/API traffic and outbound metrics-source traffic.
- Pin the container image by immutable SHA tag for deployments.
- Verify the service runs without root privileges and without write access to the root filesystem during the container smoke test.

## Evidence required

Store successful scanner and smoke-test output under `docs/evidence/member-3/pipeline/`. Redact all sensitive values before capturing logs or screenshots.
