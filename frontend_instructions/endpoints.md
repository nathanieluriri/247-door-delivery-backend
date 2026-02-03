# API Endpoints (Consumable by Frontend)
Authentication: send `Authorization: Bearer <access_token>` unless marked public.
Schemas referenced live under `schemas/` (e.g., `schemas/rider_schema.py`, `schemas/driver.py`, `schemas/ride.py`, etc.).

## Riders (/api/v1/riders)
- GET `/google/auth` → redirect to Google OAuth.
- GET `/auth/callback` → handles Google callback (sets tokens in query).
- GET `/` (auth) → list riders (admin token)
- GET `/profile` (auth rider) → returns `RiderOut`.
- POST `/signup` → body `RiderCreate`.
- POST `/login` → body `RiderBase`.
- POST `/refresh` → body `RiderRefresh`, header expired access token.
- DELETE `/account` (auth rider)
- POST `/logout` (auth rider)
- PATCH `/profile` (auth rider) → body `RiderUpdate`.
- GET `/rating` (auth rider) → `RatingOut` list.
- GET `/driver/{driverId}/rating` (auth rider)
- POST `/rate/driver` (auth rider) → body `RatingBase`.
- Address book: GET `/addresses`, POST `/address` (`AddressCreate`), PATCH `/address/{id}`, DELETE `/address/{id}`.
- Place helpers: GET `/places/autocomplete?q=`, `/places/details/{placeId}` etc. (see rider_route around lines 230-273).
- Ride history: GET `/ride/history`.
- Request ride: POST `/ride/request` → body `RideRequest` (includes pickup/destination placeIds, vehicleType, stops, schedule).
- Cancel ride: PATCH `/ride/cancel/{rideId}` → `RideUpdate` (status=canceled).
- View ride: GET `/ride/{rideId}` (auth rider).
- Share link: GET `/ride/{rideId}/share`; consume shared ride: GET `/ride/share/{shareId}`.
- Password reset: PATCH `/password-reset` (auth), POST `/password-reset/request`, PATCH `/password-reset/confirm`.

## Drivers (/api/v1/drivers)
- GET `/google/auth` / `/auth/callback` for OAuth.
- GET `/` (auth driver/admin) list drivers.
- GET `/me` (auth driver) → `DriverOut`.
- POST `/signup` → `DriverCreate`.
- POST `/login` → `DriverBase`.
- POST `/refresh` → `DriverRefresh`.
- PATCH `/profile` → `DriverUpdate`.
- POST `/location` → `DriverLocationUpdate` (lat/lon/timestamp) (required for matching).
- PUT `/vehicle` → `DriverVehicleUpdate` (vehicleType/make/model/color/plate/year).
- Documents: POST `/documents/upload` (multipart: file + `documentType`), GET `/documents`, GET `/documents/{docId}/verify`.
- Account/delete: DELETE `/account`; POST `/logout`.
- Ratings: GET `/rating`; GET `/rider/{riderId}/rating`; POST `/rate/rider`.
- Rides: POST `/ride/{ride_id}/accept`; POST `/ride/{ride_id}` (get ride details); GET `/ride/history`.
- Password reset: PATCH `/password-reset`; POST `/password-reset/request`; PATCH `/password-reset/confirm`.
- Payouts: POST `/payout/onboard`; GET `/payout/status`; GET `/payouts` (pagination query params); GET `/payout/{id}`; GET `/payout/balance`; POST `/payout/request`; POST `/payout/earn`.

## Admins (/api/v1/admins)
Auth: `login`, `signup` (admin), `refresh`, `profile`, `password-reset` trio, `delete account`.
Users:
- GET `/admins/` (paginated list)
- GET `/drivers/`, `/driver/{driverId}`; PATCH `/ban/driver/{id}`; PATCH `/approve/driver/{id}`.
- Driver documents: PATCH `/driver/{driverId}/documents/{docId}` (approve/reject).
- Background checks: PATCH `/driver/{driverId}/background`; POST `/driver/{driverId}/background/provider`; GET `/background-checks`.
- GET `/riders/`; GET `/rider/{riderId}`; PATCH `/ban/rider/{id}`.
- Search: `/users/search`, `/riders/search`.
Rides/Payments:
- POST `/ride/{userId}` (create ride for rider); GET `/ride/{riderId}`; GET `/ride/{driverId}`; PATCH `/ride/{rideId}`.
- Invoice: POST `/invoice/{rideId}`, GET `/invoice/{rideId}`.
Monitoring:
- Health: `/health`, `/health-detailed` (root, not under admins).
- Metrics: `/metrics` (root; Prometheus format).
Quarantine:
- GET `/quarantine/` (list quarantine events) [admin token]

## Payments
- Webhook: POST `/api/v1/payment/webhook` (Stripe) – backend handles; frontend only needs to display `paymentLink` or invoice URL returned in ride creation.

## SSE (Server-Sent Events)
- Driver stream: GET `/api/v1/sse/driver/stream?driver_id={driverId}` (events: `ride_request`, `ride_status_update`, `chat_message`).
- Rider stream: GET `/api/v1/sse/rider/stream?rider_id={riderId}` (events: `ride_status_update`, `ride_request`, `chat_message`).
- Ack: POST `/api/v1/sse/driver/ack`, `/api/v1/sse/rider/ack` with eventId/user ids.

## Chat (/api/v1/chat)
- POST `/` → create chat message (`ChatCreate`), returns `ChatOut`.
- GET `/stream/{ride_id}` → stream chat messages (SSE-like chunked streaming).
- GET `/{rideId}` → list chat messages for ride.
- DELETE `/{id}` → delete message.

## Notifications (client expectations)
- Ride status and ride requests arrive via SSE; push/email managed server-side.

## Key Schemas (quick reference)
- Riders: `RiderCreate`, `RiderOut`, `RiderUpdate`, `RiderRefresh`, `RiderBase`.
- Drivers: `DriverCreate`, `DriverOut`, `DriverUpdate`, `DriverVehicleUpdate`, `DriverLocationUpdate`, `DriverRefresh`, `DriverBase`.
- Rides: `RideRequest` (check rider_route), `RideOut`, `RideUpdate`, `RideShareLinkOut`.
- Payments: `InvoiceData`, `CheckoutSessionObject` (in schemas/imports.py), `StripeEvent`.
- Payouts: `PayoutCreate`, `PayoutOut`, `PayoutBalanceOut`, `PayoutRequestIn`.
- Documents: `DriverDocumentCreate/Out`, `DocumentStatus`, `DocumentType`.
- Background: `BackgroundCheckOut`, `BackgroundProviderPayload`.
- Chat: `ChatCreate`, `ChatOut`.
- Responses: all wrapped in `APIResponse[T]` with fields `status_code`, `detail`, `data`.

## Auth & Headers
- `Authorization: Bearer <access_token>` for all protected routes.
- Content types: JSON unless noted; file upload uses `multipart/form-data` with `file` and `documentType` fields.
- SSE: `Accept: text/event-stream` and keep connection open.

