#!/usr/bin/env bash
set -euo pipefail

namespace="${NAMESPACE:-kubeaiops}"
release="${RELEASE:-capacity-api}"
results_dir="${RESULTS_DIR:-docs/evidence/member-3/recovery}"
warmup_seconds="${WARMUP_SECONDS:-25}"
context="${KUBE_CONTEXT:-$(kubectl config current-context)}"
selector="app.kubernetes.io/name=demo-workload,app.kubernetes.io/instance=${release}"

if [[ "${ALLOW_POD_DELETE:-}" != "true" ]]; then
  echo "Set ALLOW_POD_DELETE=true to run this controlled recovery test." >&2
  exit 2
fi
if [[ "$context" != kind-* && "${ALLOW_NON_KIND:-}" != "true" ]]; then
  echo "Refusing to delete a pod outside a Kind context ($context). Set ALLOW_NON_KIND=true only after approval." >&2
  exit 2
fi

mkdir -p "$results_dir"
kubectl --context "$context" -n "$namespace" get deployment demo-workload >/dev/null
victim="$(kubectl --context "$context" -n "$namespace" get pods -l "$selector" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')"
if [[ -z "$victim" ]]; then
  echo "No running demo-workload pod found for selector: $selector" >&2
  exit 1
fi

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SCENARIO_REPORT="$results_dir/load-report.json" \
  k6 run --summary-export="$results_dir/k6-summary.json" load-tests/capacity/recovery/k6-recovery.js &
k6_pid=$!

cleanup() {
  if kill -0 "$k6_pid" 2>/dev/null; then
    kill "$k6_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

sleep "$warmup_seconds"
deleted_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
kubectl --context "$context" -n "$namespace" delete pod "$victim" --wait=false

deadline=$((SECONDS + 120))
replacement=""
while (( SECONDS < deadline )); do
  replacement="$(kubectl --context "$context" -n "$namespace" get pods -l "$selector" -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[0].ready}{"\n"}{end}' | awk -v victim="$victim" '$1 != victim && $2 == "true" {print $1; exit}')"
  [[ -n "$replacement" ]] && break
  sleep 2
done

if [[ -z "$replacement" ]]; then
  echo "A ready replacement pod was not observed within 120 seconds." >&2
  exit 1
fi
recovered_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
kubectl --context "$context" -n "$namespace" get pods -l "$selector" -o wide > "$results_dir/pods-after-recovery.txt"
kubectl --context "$context" -n "$namespace" get events --sort-by=.lastTimestamp > "$results_dir/events.txt"

wait "$k6_pid"
trap - EXIT
printf '{\n  "scenario": "recovery",\n  "context": "%s",\n  "namespace": "%s",\n  "victim_pod": "%s",\n  "replacement_pod": "%s",\n  "started_at": "%s",\n  "deleted_at": "%s",\n  "recovered_at": "%s"\n}\n' \
  "$context" "$namespace" "$victim" "$replacement" "$started_at" "$deleted_at" "$recovered_at" > "$results_dir/recovery-report.json"
