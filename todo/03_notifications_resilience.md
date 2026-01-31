# Notifications Resilience

## Plan
- Wire push (FCM/APNS) and SMS provider into notification service.
- Add retry with backoff + DLQ metrics and logging with ride/user context.
- Channel toggles via env, respected at runtime.

## Checks
- Push/SMS integrated and triggered on key statuses.
- Failed sends retried then DLQ'd with logs.
- Channel toggles verified in config.
