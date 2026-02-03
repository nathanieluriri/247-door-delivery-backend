# Remaining TODOs (as of 2026-01-31)

1) Integrity & AV
   - What’s left: schedule periodic hash re-verification job; admin UI/API to list/release/delete quarantined items.
   - How to do it: add APScheduler job to call `services.integrity_job.reverify_all_drivers`; extend quarantine API with release/delete actions and admin auth checks.

2) Tests & CI
   - What’s left: integration test for ride→Stripe webhook→driver assignment; GEO presence tests; load test script + docs.
   - How to do it: use pytest with Mongo/Redis fixtures or Docker services; mock Stripe webhook payloads; add k6/Locust script under `load_tests/` and document usage.

3) Notifications Resilience
   - What’s left: add metrics/logging for notification retries/DLQ, channel toggles via env, and optional SMS provider (if desired later).
   - How to do it: instrument `services/notification_service` with Prometheus counters; read toggles from env; plug in SMS provider when needed.

4) Observability
   - What’s left: finalize Grafana dashboard JSON and wire alert rules into Alertmanager; propagate correlation IDs (ride_id/driverId/riderId) into service logs beyond middleware.
   - How to do it: flesh out `dashboards/observability.json` panels; apply alert rules from `docs/alert_rules.md`; add structured logging in services emitting correlation fields.
