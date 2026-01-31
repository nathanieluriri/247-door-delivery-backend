# Observability & Alerts

## Plan
- Emit structured logs (JSON) with `ride_id`, `driverId`, `riderId`, and action names.
- Expose metrics for match time, acceptance rate, payment failures, SSE backlog; ship to Prometheus/OpenTelemetry.
- Add alert rules for payment webhook failures, zero-driver matches, and stale scheduler heartbeats.
- Create a minimal dashboard showing dispatch health and payments.

## Checks (Done When)
- Logging formatter outputs structured fields consistently across services.
- Metrics endpoint/exporter available and scraped in dev; key metrics visible.
- Alerts defined and tested for the three critical conditions.
- Dashboard saved/committed (Grafana JSON or instructions) with core panels.
