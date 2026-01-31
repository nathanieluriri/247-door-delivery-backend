# Notifications Resilience

## Plan
- Add SMS fallback for critical ride events when push/SSE fails or user offline.
- Introduce retry with dead-letter queue for notification send failures.
- Log notification attempts/outcomes for audit and debugging.
- Provide configuration toggles per channel (push/SMS/email).

## Checks (Done When)
- SMS provider integrated and triggered on key statuses (payment confirmed, driver arriving, cancel).
- Failed sends are retried with backoff and moved to DLQ after N attempts.
- Notification logs stored (DB or log stream) with ride/user context.
- Channel toggles configurable via env/settings and respected at runtime.
