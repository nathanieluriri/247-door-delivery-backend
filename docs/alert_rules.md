# Alert Rules (suggested)

- Payment webhook failures: alert when `ride_payment_failures_total` increases over 5 in 10m.
- Zero-driver matches: alert when match time p95 > 20s for 10m or ride re-dispatch counts spike.
- Scheduler heartbeat stale: alert if `/health` reports APScheduler degraded or missing heartbeat for >3 minutes.
- SSE backlog: alert when `ride_sse_pending_events` p95 > 50.

Implementation notes:
- Use Prometheus alertmanager; sample rules:
```
alert: PaymentWebhookFailures
expr: increase(ride_payment_failures_total[10m]) > 5
for: 5m
labels: { severity: "critical" }
annotations:
  summary: "High Stripe webhook failures"
```
- Create Grafana dashboard importing metrics from `/metrics`; include panels for match time histogram, payment failures, SSE backlog, scheduler heartbeat age.
