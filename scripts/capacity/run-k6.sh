#!/usr/bin/env bash
set -euo pipefail

# Prefer a locally installed k6. Docker Desktop is a supported fallback for
# development environments where the k6 binary is not installed in WSL.
if command -v k6 >/dev/null 2>&1; then
  exec k6 "$@"
fi

repo_root="$(git rev-parse --show-toplevel)"
docker_command=""
for candidate in docker docker.exe; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" version >/dev/null 2>&1; then
    docker_command="$candidate"
    break
  fi
done

if [[ -z "$docker_command" ]]; then
  echo "k6 is not installed and no working Docker client was found." >&2
  echo "Install k6 or start Docker Desktop before running a capacity scenario." >&2
  exit 127
fi

to_docker_endpoint() {
  local endpoint="$1"
  case "$endpoint" in
    http://127.0.0.1:*) echo "http://host.docker.internal:${endpoint#http://127.0.0.1:}" ;;
    http://localhost:*) echo "http://host.docker.internal:${endpoint#http://localhost:}" ;;
    *) echo "$endpoint" ;;
  esac
}

mount_root="$repo_root"
if [[ "$docker_command" == *.exe ]] && command -v wslpath >/dev/null 2>&1; then
  mount_root="$(wslpath -w "$repo_root")"
fi

base_url="$(to_docker_endpoint "${BASE_URL:-http://127.0.0.1:8001}")"
capacity_api_url="$(to_docker_endpoint "${CAPACITY_API_URL:-http://127.0.0.1:8000}")"
environment_args=(-e "BASE_URL=$base_url" -e "CAPACITY_API_URL=$capacity_api_url")

for variable in \
  SCENARIO_REPORT SLEEP_SECONDS WORK_ITERATIONS WORK_DELAY_MS RATE DURATION \
  LOW_RATE MEDIUM_RATE HIGH_RATE PEAK_RATE LOW_DURATION MEDIUM_DURATION \
  HIGH_DURATION PEAK_DURATION BASELINE_RATE SPIKE_RATE BASELINE_DURATION \
  SPIKE_DURATION RECOVERY_DURATION PRE_ALLOCATED_VUS MAX_VUS; do
  if [[ -v "$variable" ]]; then
    environment_args+=(-e "$variable=${!variable}")
  fi
done

image="${K6_DOCKER_IMAGE:-grafana/k6:0.57.0}"
echo "Running k6 with $docker_command and $image." >&2
exec "$docker_command" run --rm --network host \
  -v "$mount_root:/work" \
  -w /work \
  "${environment_args[@]}" \
  "$image" "$@"
