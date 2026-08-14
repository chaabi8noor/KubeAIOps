#!/usr/bin/env bash
set -euo pipefail

namespace="${NAMESPACE:-kubeaiops}"
context="${KUBE_CONTEXT:-$(kubectl config current-context)}"
results_dir="${RESULTS_DIR:-docs/evidence/member-3/validation}"
demo_health_url="${DEMO_HEALTH_URL:-http://127.0.0.1:8001/health}"

if [[ "${ALLOW_API_DISRUPTION:-}" != "true" ]]; then
  echo "Set ALLOW_API_DISRUPTION=true to run this controlled Capacity API resilience test." >&2
  exit 2
fi
if [[ "$context" != kind-* && "${ALLOW_NON_KIND:-}" != "true" ]]; then
  echo "Refusing to disrupt a deployment outside a Kind context ($context)." >&2
  exit 2
fi

original_replicas="$(kubectl --context "$context" -n "$namespace" get deployment capacity-api -o jsonpath='{.spec.replicas}')"
if [[ -z "$original_replicas" ]]; then
  echo "Capacity API deployment does not define replicas." >&2
  exit 1
fi

restore() {
  kubectl --context "$context" -n "$namespace" scale deployment/capacity-api --replicas="$original_replicas" >/dev/null || true
  kubectl --context "$context" -n "$namespace" rollout status deployment/capacity-api --timeout=120s >/dev/null || true
}
trap restore EXIT

capacity_has_ready_endpoint() {
  [[ -n "$(kubectl --context "$context" -n "$namespace" get endpoints capacity-api -o jsonpath='{range .subsets[*].addresses[*]}{.ip}{end}')" ]]
}

probe_capacity_from_workload() {
  local probe_pod
  probe_pod="$(kubectl --context "$context" -n "$namespace" get pods -l app.kubernetes.io/name=demo-workload --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')"
  [[ -n "$probe_pod" ]] || return 1
  kubectl --context "$context" -n "$namespace" exec "$probe_pod" -- python -c \
    'from urllib.request import urlopen; response = urlopen("http://capacity-api:8000/health/ready", timeout=3); assert response.status == 200' >/dev/null
}

mkdir -p "$results_dir"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
kubectl --context "$context" -n "$namespace" scale deployment/capacity-api --replicas=0 >/dev/null

deadline=$((SECONDS + 45))
api_unavailable=false
while (( SECONDS < deadline )); do
  if ! capacity_has_ready_endpoint; then
    api_unavailable=true
    break
  fi
  sleep 1
done

demo_available=false
if curl --fail --silent --show-error --max-time 5 "$demo_health_url" >/dev/null 2>&1; then
  demo_available=true
fi

restored_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
restore
trap - EXIT
recovered_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
recovery_status=false
deadline=$((SECONDS + 45))
while (( SECONDS < deadline )); do
  if capacity_has_ready_endpoint && probe_capacity_from_workload; then
    recovery_status=true
    break
  fi
  sleep 1
done

kubectl --context "$context" -n "$namespace" get pods -l app.kubernetes.io/name=capacity-api -o wide > "$results_dir/capacity-api-resilience-pods.txt"
kubectl --context "$context" -n "$namespace" get events --sort-by=.lastTimestamp > "$results_dir/capacity-api-resilience-events.txt"
printf '{\n  "scenario": "capacity-api-resilience",\n  "context": "%s",\n  "namespace": "%s",\n  "original_replicas": %s,\n  "started_at": "%s",\n  "api_unavailable_during_disruption": %s,\n  "demo_workload_available_during_disruption": %s,\n  "restored_at": "%s",\n  "recovered_at": "%s",\n  "capacity_api_healthy_after_restore": %s\n}\n' \
  "$context" "$namespace" "$original_replicas" "$started_at" "$api_unavailable" "$demo_available" "$restored_at" "$recovered_at" "$recovery_status" > "$results_dir/capacity-api-resilience.json"

if [[ "$api_unavailable" != true || "$demo_available" != true || "$recovery_status" != true ]]; then
  echo "Capacity API resilience test did not meet its expected outcome." >&2
  exit 1
fi
