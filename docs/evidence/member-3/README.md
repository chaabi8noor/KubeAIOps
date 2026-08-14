# Member 3 evidence

This directory separates run-specific raw output from the reviewable validation record. Never commit credentials, tokens, or environment-specific secrets.

- `k6-smoke-summary.json`, `load-tests/`, and `recovery/` are generated locally and ignored by Git.
- `validation/` contains the compact, generated result summary and controlled-resilience records retained for review.
- `api/`, `dashboard/`, `model/`, `pipeline/`, and `gitops/` are reserved for dated evidence exports from the shared platform.
- Record the branch, image tag, command, date, scenario, and conclusion with every retained result.

Generate the reviewable load-test summary from the local raw output:

```bash
make validation-evidence
```
