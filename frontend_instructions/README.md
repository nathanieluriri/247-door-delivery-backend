# Frontend Integration Guide

Numbered steps per role to consume API endpoints.

## Rider
1) Auth: Sign up/login (`/api/v1/riders/signup`, `/login`, `/refresh`), store access/refresh tokens.
2) Place search/details: use Maps client-side; submit place IDs to backend.
3) Request ride: POST `/api/v1/riders/ride/request` with pickup/destination place_ids, vehicleType; handle 404 when no drivers.
4) Listen for ride updates: open SSE `/api/v1/sse/stream/rider/{riderId}`; filter events `ride_request`, `ride_status_update`, `chat_message`.
5) Payments: follow returned `paymentLink` or invoice URL; show success page. Handle webhooks via backend—poll ride status.
6) Cancel ride: PATCH `/api/v1/riders/ride/cancel/{rideId}`.
7) Share link: GET `/api/v1/riders/ride/{rideId}/share` to show public link.
8) Rating: POST `/api/v1/riders/rate/driver` after ride completion.
9) Password reset: start/confirm via `/password-reset` routes.

## Driver
1) Auth: Signup/login (`/api/v1/drivers/signup`, `/login`, `/refresh`); obtain tokens.
2) Profile: PATCH `/api/v1/drivers/profile`; PUT `/api/v1/drivers/vehicle` to set vehicle details.
3) Documents: POST `/api/v1/drivers/documents/upload` for license/registration/insurance; GET `/documents` to view; GET `/documents/{docId}/verify` for integrity check.
4) Background status: activation requires admin approval and PASSED background; show accountStatus from `/drivers/me`.
5) Go online/share location: POST `/api/v1/drivers/location` periodically with lat/lon; required before matches.
6) Ride offers: subscribe SSE `/api/v1/sse/stream/driver/{driverId}` for `ride_request` and `ride_status_update` events.
7) Accept ride: POST `/api/v1/drivers/ride/{rideId}/accept`; fetch ride details `/api/v1/drivers/ride/{rideId}`.
8) Earnings/payouts: onboard `/payout/onboard`, status `/payout/status`, list `/payouts`, request `/payout/request`, balance `/payout/balance`.
9) Password reset/logout via respective endpoints.

## Admin
1) Auth: Login `/api/v1/admins/login`; use token for all admin endpoints.
2) Users: list/search riders/drivers (`/admins/riders/`, `/admins/drivers/`, search endpoints); view single user.
3) Driver compliance: approve/ban (`/approve/driver/{id}`, `/ban/driver/{id}`); review documents `/driver/{driverId}/documents/{docId}`; background checks list `/background-checks` and update `/driver/{driverId}/background`.
4) Rider moderation: ban rider `/ban/rider/{id}`.
5) Rides: create ride for user `/ride/{userId}`; update rides via admin routes; view ride lists.
6) Payments: handled by backend; monitor via health endpoints.
7) Monitoring: `/health`, `/health-detailed`, metrics at `/metrics`.
8) Audit: actions logged automatically; surface statuses to admins.

General
- Include bearer `Authorization: Bearer <access_token>` where required.
- Handle 401/403 by refreshing tokens or redirecting to login.
- SSE clients should reconnect and may use Last-Event-ID if stored.
