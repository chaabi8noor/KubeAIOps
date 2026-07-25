import {
  duration,
  positiveInteger,
  scenarioReport,
  sendWorkloadRequest,
  setupCapacityApi,
  thresholds,
} from "../lib/common.js";

const lowRate = positiveInteger("LOW_RATE", 10);
const mediumRate = positiveInteger("MEDIUM_RATE", 30);
const highRate = positiveInteger("HIGH_RATE", 60);
const peakRate = positiveInteger("PEAK_RATE", 90);
const stages = [
  { name: "low", target: lowRate, duration: duration("LOW_DURATION", "20s") },
  { name: "medium", target: mediumRate, duration: duration("MEDIUM_DURATION", "20s") },
  { name: "high", target: highRate, duration: duration("HIGH_DURATION", "20s") },
  { name: "peak", target: peakRate, duration: duration("PEAK_DURATION", "20s") },
];

export const options = {
  scenarios: {
    progressive: {
      executor: "ramping-arrival-rate",
      startRate: lowRate,
      timeUnit: "1s",
      preAllocatedVUs: positiveInteger("PRE_ALLOCATED_VUS", 20),
      maxVUs: positiveInteger("MAX_VUS", 100),
      stages: stages.map((stage) => ({ duration: stage.duration, target: stage.target })),
    },
  },
  thresholds,
};

export const setup = setupCapacityApi;

export default function () {
  sendWorkloadRequest("progressive");
}

export const handleSummary = scenarioReport("progressive", stages);
