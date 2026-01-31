# Testing & CI

## Plan
- Add pytest integration tests covering ride request → payment webhook → driver assignment.
- Add unit tests for Redis GEO driver discovery filters and stale cleanup job.
- Create lightweight load test for dispatch concurrency (Locust or k6) with doc.
- Wire CI workflow to run unit/integration suites on PRs.

## Checks (Done When)
- `pytest` suite exists and passes locally.
- GEO presence tests assert filtering by status/profile and TTL cleanup.
- Load test script exists with README on running; produces basic RPS/latency output.
- CI pipeline executes tests on every push/PR and fails on regressions.
