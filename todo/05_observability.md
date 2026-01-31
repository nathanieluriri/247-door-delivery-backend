# Observability

## Plan
- Add domain metrics (match time, acceptance rate, payment failures, SSE backlog) and expose via `/metrics`.
- Create alert rules (payment webhook failures, zero-driver matches, stale scheduler heartbeat) and commit dashboard asset/guide.
- Enrich logs with correlation IDs (ride_id, driverId, riderId) across services.

## Checks
- Metrics counters/histograms present and scrapeable. **(Done)**
- Alert rules documented/configured; dashboard asset committed.
- Logs include correlation fields consistently.
