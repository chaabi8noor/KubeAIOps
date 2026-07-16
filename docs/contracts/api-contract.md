# Member 3 Capacity API Contract

| Field | Decision |
| --- | --- |
| Status | Proposed for Step 1 review |
| Owner | Member 3 - Capacity AIOps Engineer |
| Reviewers | All members; Member 1 reviews monitoring behavior |
| Change control | Removing or renaming a field is a breaking change and requires a reviewed merge request. |

## Scope

The Capacity API forecasts near-term workload pressure and recommends a bounded replica count. It does **not** modify Kubernetes objects or replace HPA/KEDA. Kubernetes autoscaling remains the agreed control mechanism.

Base path: `/api/v1`

## Endpoints

| Method | Path | Contract |
| --- | --- | --- |
| `GET` | `/health` | Composite health summary for operators. |
| `GET` | `/health/live` | The process and event loop are running. It must not depend on Prometheus. |
| `GET` | `/health/ready` | Model, configuration, and required prediction dependencies are usable. |
| `GET` | `/metrics` | Prometheus text-format metrics defined by the metrics contract. |
| `GET` | `/api/v1/capacity/{workload}/recommendation` | Returns the latest capacity recommendation for one workload. |

`{workload}` must be a DNS-label-style identifier: lowercase letters, digits, and hyphens; it must start and end with an alphanumeric character and be at most 63 characters. Invalid syntax returns `422` before any metrics lookup.

## Successful recommendation response

`200 OK` returns this stable shape:

```json
{
  "stream": "capacity",
  "target": "demo-workload",
  "status": "warning",
  "score": 0.82,
  "evidence": {
    "current_requests_per_second": 74.2,
    "forecast_requests_per_second": 121.5,
    "current_replicas": 2,
    "cpu_utilization": 0.78,
    "forecast_horizon_seconds": 60
  },
  "recommendation": {
    "replicas": 4,
    "action": "scale_up",
    "reason": "Forecast demand exceeds safe current capacity"
  },
  "model_version": "capacity-forecast-v1",
  "timestamp": "2026-07-16T12:00:00Z"
}
```

| Field | Type | Rules |
| --- | --- | --- |
| `stream` | string | Always `capacity`. |
| `target` | string | Echoes the validated workload identifier. |
| `status` | string | One of `normal`, `warning`, `critical`, or `unknown`. |
| `score` | number | Model/policy pressure score in the inclusive range 0 to 1. |
| `evidence` | object | Contains the current observations and forecast used by the decision. New optional fields may be added. |
| `recommendation.replicas` | integer | Always within configured `MIN_REPLICAS` and `MAX_REPLICAS` for successful decisions. |
| `recommendation.action` | string | One of `hold`, `scale_up`, `scale_down`, or `insufficient_data`. |
| `recommendation.reason` | string | Concise, operator-readable reason. It must not contain secrets or uncontrolled upstream error text. |
| `model_version` | string | Loaded model artifact version. |
| `timestamp` | string | UTC RFC 3339 timestamp for the decision. |

The initial forecast horizon of 60 seconds is provisional pending measured k6 results. The field remains required regardless of the selected horizon.

## Failure response and HTTP behavior

All non-success responses use the following envelope:

```json
{
  "detail": {
    "code": "metrics_unavailable",
    "message": "Recent workload metrics are unavailable",
    "target": "demo-workload"
  }
}
```

| Situation | HTTP status | `detail.code` |
| --- | --- | --- |
| Invalid workload syntax | `422` | `invalid_workload` |
| Known syntax but unknown workload | `404` | `workload_not_found` |
| Insufficient recent metrics | `503` | `insufficient_metrics` |
| Prometheus or metrics source unavailable | `503` | `metrics_unavailable` |
| Model artifact or required configuration unavailable | `503` | `model_unavailable` |
| Controlled prediction failure | `500` | `prediction_failed` |
| Unexpected internal failure | `500` | `internal_error` |

For a missing-data condition, the endpoint must not invent a numeric replica recommendation. It returns `503` with a controlled code; the corresponding metric failure counter must be incremented.

## Health behavior

- `/health/live` returns `200` when the process is responsive, otherwise `503`.
- `/health/ready` returns `200` only after startup validation has loaded the model, parsed configuration, and completed a safe test prediction; otherwise it returns `503`.
- `/health` returns `200` when ready and `503` when any required prediction dependency is unavailable. Its body may add diagnostic fields but must include a `status` field.

## Compatibility and security rules

- Keep the API under `/api/v1/` until a reviewed v2 is introduced.
- New response fields must be optional to existing consumers.
- Validate path input before passing it to a query, file system, or shell operation.
- Do not return secrets, connection strings, raw Prometheus responses, stack traces, or model internals in error responses.
- Contract tests must cover one success response and every HTTP behavior in this document.
