# Driver Location Flow (Nearby Driver Matching)

This document explains how a driver’s location is set, stored, and used to find nearby drivers during ride creation.

## 1) Where driver location is set

**Endpoint**
- `POST /api/v1/driver/location` (see `api/v1/driver.py`)

**Request body**
- `DriverLocationUpdate` with `latitude`, `longitude`, and optional `timestamp` (see `schemas/driver.py`).

**Guards/requirements**
The location update is rejected unless all of the following pass:
- `check_driver_account_status`: driver must exist and `accountStatus == ACTIVE` (see `security/account_status_checks.py`).
- `check_driver_sse_eligibility`: driver must be eligible to use SSE (see `security/account_status_checks.py`). Eligibility requires:
  - `accountStatus == ACTIVE`
  - `vehicleVerified == True`
  - Latest documents approved for: `DRIVER_LICENSE`, `VEHICLE_REGISTRATION`, `INSURANCE`, `BACKGROUND_CHECK`
- `update_driver_location` in `services/driver_service.py` also verifies:
  - `profileComplete == True` (vehicle details set)

If any of those fail, the driver’s location is **not** stored in Redis.

## 2) How location is stored

Location updates call `update_driver_presence()` in `services/sse_service.py` which performs two writes to Redis:

1) **Geo index** (for spatial search)
- Key: `drivers:geo_index` (configurable via `DRIVER_GEO_INDEX`, default `drivers:geo_index`)
- Command: `GEOADD`
- Value: driver ID with `(longitude, latitude)`

2) **Presence metadata** (for filtering)
- Key: `sse:driver_presence:{driver_id}`
- Stored fields:
  - `vehicle_type` (normalized)
  - `latitude`
  - `longitude`
  - `last_seen` (unix timestamp)
  - `profile_complete`
  - `account_status`
- TTL: `DRIVER_META_TTL_SECONDS` (default 120 seconds)

**Important**: the presence hash expires quickly (default 2 minutes). If the driver does not keep sending location updates, they will be treated as stale.

## 3) How “nearby drivers” are found

There are two slightly different flows using the same geo index:

1) **Simple nearby count** (rider flow)
- Function: `services/place_service.py:nearby_drivers()`
- Redis: `GEORADIUS drivers:geo_index` within `5.0 km`
- Returns only the number of nearby IDs (no metadata filtering)

2) **Ride request dispatch** (SSE broadcast)
- Function: `services/sse_service.py:publish_ride_request_to_drivers()`
- Redis: `GEORADIUS drivers:geo_index` within `DRIVER_DISCOVERY_RADIUS_KM` (default 5 km)
- Additional filtering uses driver presence metadata:
  - `account_status` must be `active`
  - `profile_complete` must be true
  - vehicle type must match requested vehicle type (if provided)
  - `last_seen` must be within `DRIVER_META_TTL_SECONDS`

If any of those checks fail, the driver is excluded even if they are inside the radius.

## 4) When driver presence is removed

Driver presence can be removed in two ways:
- **TTL expiry**: the presence hash expires if no updates arrive within `DRIVER_META_TTL_SECONDS`.
- **SSE disconnect**: when the driver SSE stream closes, the `stream_events()` cleanup deletes the driver presence and removes them from the subscriber set.

## 5) Common reasons a driver is “nearby” but not shown

If a rider sees no drivers even though one should be nearby, check these first:

- The driver never called `POST /api/v1/driver/location`, or the call failed.
- The driver is not **SSE eligible** (vehicle not verified, documents not approved, account not active).
- `profileComplete` is false (vehicle details not set).
- The driver’s location update stopped and their presence expired (default 120 seconds).
- The requested vehicle type does not match the driver’s `vehicle_type`.
- The ride pickup location is missing or invalid (no lat/lng), so dispatch can’t run.

## 6) Practical debugging checklist

- Confirm driver eligibility: `GET /api/v1/sse/driver/eligibility`.
- Ensure driver has updated location recently (within 120s).
- Verify `drivers:geo_index` contains the driver ID.
- Verify `sse:driver_presence:{driver_id}` exists and has `last_seen`, `latitude`, `longitude`.
- Confirm pickup lat/lng are present in the ride request.
- Confirm `vehicle_type` requested matches driver’s vehicle.

## Key files

- `api/v1/driver.py` (location endpoint)
- `services/driver_service.py` (validation + update call)
- `services/sse_service.py` (Redis geo + presence)
- `security/account_status_checks.py` (eligibility rules)
- `services/place_service.py` (nearby count)
