import {
  duration,
  positiveInteger,
  scenarioReport,
  sendWorkloadRequest,
  setupCapacityApi,
  thresholds,
} from "../lib/common.js";

const rate = positiveInteger("RATE", 75);
const testDuration = duration("DURATION", "2m");

export const options = {
  scenarios: {
    sustained: {
      executor: "constant-arrival-rate",
      rate,
      timeUnit: "1s",
      duration: testDuration,
      preAllocatedVUs: positiveInteger("PRE_ALLOCATED_VUS", 30),
      maxVUs: positiveInteger("MAX_VUS", 120),
    },
  },
  thresholds,
};

export const setup = setupCapacityApi;

export default function () {
  sendWorkloadRequest("sustained");
}

export const handleSummary = scenarioReport("sustained", [
  { name: "high_stability_load", target: rate, duration: testDuration },
]);
