import http from "k6/http";
import { check, sleep } from "k6";

const workloadBaseUrl = __ENV.BASE_URL || "http://127.0.0.1:8001";
const capacityApiUrl = __ENV.CAPACITY_API_URL || "http://127.0.0.1:8000";

export const options = {
  scenarios: {
    smoke: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 2),
      duration: __ENV.DURATION || "10s",
    },
  },
  thresholds: {
    checks: ["rate==1"],
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<1000"],
  },
};

export function setup() {
  const response = http.get(
    `${capacityApiUrl}/api/v1/capacity/demo-workload/recommendation`,
  );
  check(response, {
    "capacity recommendation endpoint returns 200": (result) => result.status === 200,
  });
}

export default function () {
  const response = http.get(`${workloadBaseUrl}/work?iterations=10000`, {
    headers: { "X-KubeAIOps-Scenario": "normal" },
  });

  check(response, {
    "demo workload returns 200": (result) => result.status === 200,
    "demo workload returns its name": (result) =>
      result.json("workload") === "demo-workload",
  });
  sleep(0.2);
}
