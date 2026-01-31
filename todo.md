# MVP Checklist (Country-Scale Launch, Stripe Payments, No Drivers Yet)

This checklist focuses on backend readiness for a country-wide MVP rollout.

## 1) Driver Onboarding & Compliance

- Driver registration with full profile + vehicle details (already added).
- Document upload + verification workflow:
  - Driver license
  - Vehicle registration
  - Insurance
  - Optional background check
- Admin review + approval statuses:
  - `PENDING_VERIFICATION` → `ACTIVE` or `REJECTED`
- Prevent ride requests from reaching unverified drivers.

## 2) Driver Location & Availability

- Real-time driver location updates (REST heartbeat or WebSocket).
- Persist last location in Redis GEO index.
- Define driver availability (online/offline) and exclude offline drivers.
- Location TTL: expire stale drivers.

## 3) Ride Matching & Dispatch

- Matching based on:
  - Vehicle type
  - Driver availability
  - Distance (radius)
  - Optional ranking (ratings, acceptance rate)
- Reject ride creation if no nearby drivers.
- Retry / re-dispatch strategy if no driver accepts in X seconds.

## 4) Ride Lifecycle Enforcement

- Strict ride status transitions (already partially done).
- Concurrency protection:
  - Prevent multiple drivers accepting same ride.
  - Reject acceptance if ride already assigned/canceled.
- Timers for:
  - Finding driver timeout
  - Pickup timeout
  - Ride start timeout

## 5) Payments (Stripe)

- Stripe payment intent lifecycle:
  - Authorize on request
  - Capture on completion
  - Cancel on timeout/no-show
- Payment status sync with ride status.
- Refund / partial refund flow.
- Avoid charging before driver acceptance.

## 6) Pricing Integrity

- All pricing computed server-side.
- Store original pricing inputs for audit.
- Prevent client-tampered pricing.

## 7) Notifications

- Push notifications (driver + rider).
- SMS fallback for key ride status updates.
- Email receipts after completion.

## 8) Safety & Trust

- Rate limiting for ride requests.
- Abuse / fraud detection (spam, cancellations).
- Ban/suspend flows and audit logs.

## 9) Monitoring & Observability

- Logs with ride_id correlation.
- Metrics for:
  - Avg match time
  - Driver acceptance rate
  - Ride completion rate
- Alerting on failed payments, dispatch errors.

## 10) Admin Tools

- Admin dashboard endpoints:
  - Driver approval
  - Ride audits
  - Refund triggers
- Audit trail for admin actions.

## 11) API Docs + Client Contracts

- Updated OpenAPI / docs for:
  - Driver vehicle update
  - Driver location update
  - SSE filtering behavior

## 12) Testing

- Integration tests for:
  - Ride request → accept → complete
  - Payment success/failure
  - Driver discovery filtering
- Load testing basic dispatch under concurrency.
