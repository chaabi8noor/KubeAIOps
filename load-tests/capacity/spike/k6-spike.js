import {
  duration,
  positiveInteger,
  scenarioReport,
  sendWorkloadRequest,
  setupCapacityApi,
  thresholds,
} from "../lib/common.js";

const baselineRate = positiveInteger("BASELINE_RATE", 12);
const spikeRate = positiveInteger("SPIKE_RATE", 120);
const stages = [
  { name: "baseline", target: baselineRate, duration: duration("BASELINE_DURATION", "20s") },
  { name: "spike", target: spikeRate, duration: duration("SPIKE_DURATION", "30s") },
  { name: "recovery", target: baselineRate, duration: duration("RECOVERY_DURATION", "20s") },
];

export const options = {
  scenarios: {
    spike: {
      executor: "ramping-arrival-rate",
      startRate: baselineRate,
      timeUnit: "1s",
      preAllocatedVUs: positiveInteger("PRE_ALLOCATED_VUS", 30),
      maxVUs: positiveInteger("MAX_VUS", 150),
      stages: stages.map((stage) => ({ duration: stage.duration, target: stage.target })),
    },
  },
  thresholds,
};

export const setup = setupCapacityApi;

export default function () {
  sendWorkloadRequest("spike");
}

export const handleSummary = scenarioReport("spike", stages);
