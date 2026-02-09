# Driver Ride Lifecycle Endpoints

This document lists the **current** driver-facing API endpoints used to move a ride through its lifecycle and clarifies what is **missing** for start/complete.

## Current driver endpoints

### 1) Accept a ride (moves to `arrivingToPickup`)

**Endpoint**
- `POST /api/v1/driver/ride/{ride_id}/accept`

**Auth**
- Driver token required
- SSE eligibility required

**Effect**
- Assigns `driverId` to the ride
- Transitions status: `findingDriver` → `arrivingToPickup`

**Notes**
- This is the only driver endpoint that changes ride status.

### 2) Start a ride (moves to `drivingToDestination`)

**Endpoint**
- `POST /api/v1/driver/ride/{ride_id}/start`

**Auth**
- Driver token required
- SSE eligibility required

**Effect**
- Transitions status: `arrivingToPickup` → `drivingToDestination`

### 3) Complete a ride (moves to `completed`)

**Endpoint**
- `POST /api/v1/driver/ride/{ride_id}/complete`

**Auth**
- Driver token required
- SSE eligibility required

**Effect**
- Transitions status: `drivingToDestination` → `completed`

### 2) Record earnings (requires completed ride)

**Endpoint**
- `POST /api/v1/driver/payout/earn`

**Auth**
- Driver token required

**Effect**
- Records payout once a ride is already `completed`

**Notes**
- This does **not** change the ride status.

## Notes
- Status transitions are validated by `services.ride_service.update_ride_by_id(...)`.
- If the ride is not in the expected state, the endpoint returns `400` with an invalid transition error.
