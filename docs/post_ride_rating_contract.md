# Mandatory Post-Ride Rating Contract

## Purpose
Frontend apps must enforce rating completion before users continue core ride operations.
Backend is the source of truth for lock/unlock.

## Rating Endpoints
- Rider rates driver: `POST /api/v1/riders/rate/driver`
- Driver rates rider: `POST /api/v1/drivers/rate/rider`

Each submit must include:
- `rideId`
- `userId` (the person being rated)
- `rating` (`1..5`)

Backend validation:
- Requesting user must belong to that ride (rider or assigned driver).
- Rated `userId` must match the ride counterparty.
- One rating per `(rideId, raterId)` (duplicate returns `409`).

## Ride Payload Contract
`ratingStatus` is now included in `RideOut` responses (history/details and other ride retrievals):

```json
{
  "ratingStatus": {
    "riderMustRate": true,
    "driverMustRate": true,
    "riderRated": false,
    "driverRated": false,
    "riderRatedAt": null,
    "driverRatedAt": null
  }
}
```

`ratingStatus` is also available in SSE `ride_status_update` payloads as `ratingStatus`.

## Gate Rules
- Rider gate condition: `riderMustRate && !riderRated`
- Driver gate condition: `driverMustRate && !driverRated`

## Backend-Enforced Blocking
### Rider
When rider has pending rating, backend blocks:
- `POST /api/v1/riders/ride/request`

Returned error:
- `403` with `detail.code = "RATING_REQUIRED_RIDER"`
- `detail.rideId` contains the blocking ride.

### Driver
When driver has pending rating, backend blocks operational flow via SSE eligibility checks:
- `GET /api/v1/sse/driver/stream`
- Endpoints depending on driver SSE eligibility (location update, accept/start/complete ride).

Eligibility reasons include:
- `RATING_REQUIRED_DRIVER: rate ride <rideId> before going online`

## Allowed While Blocked
Backend still allows:
- profile endpoints
- support/help endpoints
- ride history
- ride details
- logout
- rating submission endpoint

## Frontend Integration Notes
- Do not unlock UI until backend confirms rated status from fresh ride payload/SSE.
- On app restart/new device, recompute lock from backend ride payloads.
- If rating submit fails, keep gate active and prompt retry.
