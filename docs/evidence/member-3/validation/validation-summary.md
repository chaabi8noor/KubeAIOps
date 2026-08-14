# Capacity validation summary

Source commit: `f0d50292ae11078916dcb600ad4221efc17e671a`.

This file is generated from local k6 output. It records measured results; it does not replace dashboard or alert review.

| Scenario | Status | Requests | Failed-request rate | p95 latency (ms) | Checks |
| --- | --- | ---: | ---: | ---: | --- |
| normal | passed | 361 | 0 | 16.30618 | 721 passed / 0 failed |
| progressive | passed | 3000 | 0 | 14.65142555 | 5999 passed / 0 failed |
| spike | passed | 3512 | 0 | 283.37395645 | 7023 passed / 0 failed |
| sustained | passed | 9001 | 0 | 11.083947 | 18001 passed / 0 failed |
| pod-failure | passed | 3601 | 0 | 10.645519 | 7201 passed / 0 failed |

A `not-run` or `incomplete` result is an evidence gap, not a passing result.
