import {
  duration,
  positiveInteger,
  scenarioReport,
  sendWorkloadRequest,
  setupCapacityApi,
  thresholds,
} from "../lib/common.js";

const rate = positiveInteger("RATE", 40);
const testDuration = duration("DURATION", "90s");

export const options = {
  scenarios: {
    recovery: {
      executor: "constant-arrival-rate",
      rate,
      timeUnit: "1s",
      duration: testDuration,
      preAllocatedVUs: positiveInteger("PRE_ALLOCATED_VUS", 20),
      maxVUs: positiveInteger("MAX_VUS", 100),
    },
  },
  thresholds,
};

export const setup = setupCapacityApi;

export default function () {
  sendWorkloadRequest("recovery");
}

export const handleSummary = scenarioReport("recovery", [
  { name: "continuous_traffic_during_pod_replacement", target: rate, duration: testDuration },
]);
