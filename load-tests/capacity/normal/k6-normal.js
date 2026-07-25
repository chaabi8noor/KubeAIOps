import {
  duration,
  positiveInteger,
  scenarioReport,
  sendWorkloadRequest,
  setupCapacityApi,
  thresholds,
} from "../lib/common.js";

const rate = positiveInteger("RATE", 12);
const testDuration = duration("DURATION", "30s");

export const options = {
  scenarios: {
    normal: {
      executor: "constant-arrival-rate",
      rate,
      timeUnit: "1s",
      duration: testDuration,
      preAllocatedVUs: positiveInteger("PRE_ALLOCATED_VUS", 10),
      maxVUs: positiveInteger("MAX_VUS", 30),
    },
  },
  thresholds,
};

export const setup = setupCapacityApi;

export default function () {
  sendWorkloadRequest("normal");
}

export const handleSummary = scenarioReport("normal", [
  { name: "controlled_normal_load", target: rate, duration: testDuration },
]);
