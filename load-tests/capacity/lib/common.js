import http from "k6/http";
import { check, sleep } from "k6";

export const workloadBaseUrl = __ENV.BASE_URL || "http://127.0.0.1:8001";
export const capacityApiUrl = __ENV.CAPACITY_API_URL || "http://127.0.0.1:8000";

const runStartedAt = new Date();

export const thresholds = {
  http_req_failed: ["rate<0.02"],
  http_req_duration: ["p(95)<1000"],
};

export function positiveInteger(name, fallback) {
  const value = Number(__ENV[name] || fallback);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}

export function nonNegativeInteger(name, fallback) {
  const configured = __ENV[name];
  const value = configured === undefined ? fallback : Number(configured);
  return Number.isInteger(value) && value >= 0 ? value : fallback;
}

export function duration(name, fallback) {
  return __ENV[name] || fallback;
}

export function setupCapacityApi() {
  const response = http.get(
    `${capacityApiUrl}/api/v1/capacity/demo-workload/recommendation`,
  );
  check(response, {
    "capacity API is reachable": (result) => result.status === 200,
    "capacity API returns a recommendation": (result) =>
      result.status === 200 && result.json("recommendation.action") === "hold",
  });
}

export function sendWorkloadRequest(scenario) {
  const iterations = positiveInteger("WORK_ITERATIONS", 10000);
  const delayMs = nonNegativeInteger("WORK_DELAY_MS", 0);
  const response = http.get(
    `${workloadBaseUrl}/work?iterations=${iterations}&delay_ms=${delayMs}`,
    { headers: { "X-KubeAIOps-Scenario": scenario } },
  );

  check(response, {
    "demo workload returns 200": (result) => result.status === 200,
    "demo workload returns its name": (result) =>
      result.status === 200 && result.json("workload") === "demo-workload",
  });
  sleep(Number(__ENV.SLEEP_SECONDS || 0.05));
}

function durationMilliseconds(value) {
  const match = /^(\d+)(ms|s|m|h)$/.exec(value);
  if (!match) {
    return 0;
  }
  const amount = Number(match[1]);
  const unit = match[2];
  return amount * (unit === "h" ? 3600000 : unit === "m" ? 60000 : unit === "s" ? 1000 : 1);
}

export function scenarioReport(scenario, stages) {
  return function handleSummary(data) {
    let elapsed = 0;
    const stageTimeline = stages.map((stage) => {
      const startedAt = new Date(runStartedAt.getTime() + elapsed).toISOString();
      elapsed += durationMilliseconds(stage.duration);
      return {
        name: stage.name,
        target_rate_per_second: stage.target,
        duration: stage.duration,
        started_at: startedAt,
      };
    });
    const report = {
      scenario,
      started_at: runStartedAt.toISOString(),
      finished_at: new Date().toISOString(),
      stages: stageTimeline,
      metrics: data.metrics,
    };
    const output =
      __ENV.SCENARIO_REPORT ||
      `docs/evidence/member-3/load-tests/${scenario}-report.json`;
    return { [output]: JSON.stringify(report, null, 2) };
  };
}
