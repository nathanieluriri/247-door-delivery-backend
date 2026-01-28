# Driver App Flow (Frontend Integration Guide)

Use `base_url` as the environment-specific API origin. All endpoints below are shown as `base_url/endpoint`.

## 1) Authentication and Session

- Sign up: `POST base_url/api/v1/drivers/signup`
- Log in: `POST base_url/api/v1/drivers/login`
- Refresh token: `POST base_url/api/v1/drivers/refresh` (send expired access token in `Authorization: Bearer <token>` and refresh token in body)
- Log out: `POST base_url/api/v1/drivers/logout`

Store `accessToken` and `refreshToken` from the auth responses. Use `Authorization: Bearer <accessToken>` for all protected routes.

## 2) Driver Profile and Account

- Get current driver: `GET base_url/api/v1/drivers/me`
- Update profile: `PATCH base_url/api/v1/drivers/profile`
- Delete account: `DELETE base_url/api/v1/drivers/account`
- View driver rating: `GET base_url/api/v1/drivers/rating`

## 3) Driver Onboarding (Payments)

After the driver account is created and profile is ready, onboard the driver for payouts:

- Start Stripe Connect onboarding: `POST base_url/api/v1/drivers/payout/onboard`
- Check onboarding status/eligibility: `GET base_url/api/v1/drivers/payout/status`

The frontend should treat onboarding as required for an active driver account:

- On login (and periodically), call `GET base_url/api/v1/drivers/payout/status` to determine whether the driver is fully onboarded.
- If not onboarded/eligible, block ride acceptance UI and route the driver to complete onboarding via `POST base_url/api/v1/drivers/payout/onboard`.

## 3) Ride Requests (Real-Time)

Drivers receive ride requests via SSE. The frontend should open an SSE stream after login.

- Global driver stream: `GET base_url/api/v1/sse/driver/stream`
  - Optional query params:
    - `event_types=ride_request&event_types=ride_status_update`
    - `ride_id=<ride_id>`

Alternatively, you can use the driver ride stream:
- `GET base_url/api/v1/drivers/ride/events`

Each SSE message has `id`, `event`, and `data`. Events must be acknowledged.

- Acknowledge events: `POST base_url/api/v1/sse/driver/ack` with body `{ "eventId": "<event_id>" }`

## 3.1) SSE Schemas (Event Payloads)

These are the payloads carried inside `SSEEvent.data` (see `schemas/sse.py`):

- `SSEEvent`: `id: str`, `event: str`, `data: object`, `createdAt: int`
- `SSEAck`: `{ "eventId": "<event_id>" }`
- `RideRequestEvent` (event: `ride_request`): `rideId`, `pickup`, `destination`, `vehicleType`, `fareEstimate?`, `riderId?`
- `RideStatusUpdate` (event: `ride_status_update`): `rideId`, `status`, `message?`, `etaMinutes?`
- `ChatMessageEvent` (event: `chat_message`): `chatId`, `rideId`, `senderId`, `senderType`, `message`, `timestamp`

## 4) Accepting a Ride

When a `ride_request` event is received:

1. Confirm the driver is onboarded (via `GET base_url/api/v1/drivers/payout/status`). If not, block acceptance and prompt onboarding.
1. Show pickup/destination/vehicle/fare info to the driver.
2. On accept, call:
   - `POST base_url/api/v1/drivers/ride/{ride_id}/accept`
3. The server assigns the driver and updates the ride status to `arrivingToPickup`.

## 5) Active Ride Monitoring

After accepting a ride, you can subscribe to ride-specific updates:

- `GET base_url/api/v1/drivers/ride/{ride_id}/monitor`

This stream emits `ride_status_update` and `chat_message` events for that ride. Acknowledge each event using the SSE ack endpoint.

## 6) Ride Details and History

- Get ride details: `POST base_url/api/v1/drivers/ride/{ride_id}`
- List ride history: `GET base_url/api/v1/drivers/ride/history`

## 7) Ratings

After a completed ride, allow the driver to rate the rider:

- Rate rider: `POST base_url/api/v1/drivers/rate/rider`
  - Body: `{ "rideId": "<ride_id>", "userId": "<rider_id>", "rating": 1-5 }`
- View a rider's rating: `GET base_url/api/v1/drivers/rider/{riderId}/rating`

## 8) Password Reset

- Request reset: `POST base_url/api/v1/drivers/password-reset/request`
- Confirm reset: `PATCH base_url/api/v1/drivers/password-reset/confirm`
- Change password (logged in): `PATCH base_url/api/v1/drivers/password-reset`

## 9) Payouts and Earnings

Use these endpoints to handle driver earnings and withdrawals:

- Start Stripe Connect onboarding: `POST base_url/api/v1/drivers/payout/onboard`
- Check payout eligibility: `GET base_url/api/v1/drivers/payout/status`
- List payouts: `GET base_url/api/v1/drivers/payouts` (supports `start/stop` or `page_number` query params)
- Get payout detail: `GET base_url/api/v1/drivers/payout/{id}`
- Get available balance: `GET base_url/api/v1/drivers/payout/balance`
- Request payout: `POST base_url/api/v1/drivers/payout/request`
- Record ride earnings (typically automatic): `POST base_url/api/v1/drivers/payout/earn`

## 10) Expected Ride Status Updates

The SSE `ride_status_update` event includes the current status. Common statuses:

- `pendingPayment`
- `findingDriver`
- `arrivingToPickup`
- `drivingToDestination`
- `canceled`
- `completed`

Use these to drive UI state transitions in the driver app.

## 11) Driver App Schemas (Requests/Responses)

Schema sources are in `schemas/*.py`. Commonly used fields:

- Auth/Profile: `DriverBase` (email, password), `DriverCreate` (+firstName?, lastName?), `DriverUpdate` (firstName?, lastName?), `DriverUpdatePassword` (password), `DriverRefresh` (refreshToken), `DriverOut` (id, email, firstName, lastName, stripeAccountId?, accountStatus, accessToken?, refreshToken?, dateCreated, lastUpdated)
- Rides: `RideUpdate` (driverId?, rideStatus?), `RideOut` (id, pickup, destination, vehicleType, rideStatus, driverId?, userId, price?, paymentStatus, paymentLink?, origin?, map?, dateCreated, lastUpdated)
- Ratings: `RatingBase` (rideId, userId, rating 1-5), `RatingOut` (+id, raterId, dateCreated, lastUpdated), `RatingSummary` (avgRating, totalRides)
- Payouts: `PayoutRequestIn` (amount, description?, instant), `PayoutOut` (payoutOption, amount, rideIds, driverId, id, dateCreated, lastUpdated), `PayoutBalanceOut` (currency, availableBalance, totalWithdrawn, totalEarnings)
- Chat: `ChatBase` (rideId, text), `ChatOut` (+id, dateCreated, lastUpdated)

Key enums used in driver flows: `RideStatus`, `PayoutOptions`, `UserType`, `AccountStatus`, `VehicleType`.
