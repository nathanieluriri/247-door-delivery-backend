# Tests & CI

## Plan
- Integration test: ride request → Stripe webhook → driver assignment (mocked Stripe/Redis/Mongo).
- GEO presence tests for status/profile filters and TTL cleanup.
- Load test script (k6/Locust) for dispatch concurrency with doc.

## Checks
- Integration suite passes locally.
- GEO tests validate filters/cleanup.
- Load test script committed with usage docs.
