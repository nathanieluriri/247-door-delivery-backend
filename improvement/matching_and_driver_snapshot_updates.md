# Matching, Driver Snapshot, and SSE Updates

## Summary
This document captures the latest dispatch and rider-visibility changes:

1. Instant matching now has a hard timeout (no infinite matching loop).
2. Ride request availability and dispatch are now strict on requested vehicle type.
3. Driver geo updates now overwrite old coordinates (no stale first-location lock).
4. Driver onboarding eligibility now requires an approved headshot document.
5. Rider SSE and ride polling now include richer driver snapshot data, including rating.

## 1) Driver Eligibility Requirement (Headshot)

Driver SSE/operational eligibility now requires these approved documents:

- `driver_license`
- `vehicle_registration`
- `insurance`
- `background_check`
- `driver_headshot`

If any required document is missing/unapproved, the driver is not eligible for location/ride operational flow that depends on SSE eligibility checks.

## 2) Matching Algorithm Changes

### 2.1 Instant ride matching timeout

Non-scheduled rides in `matching` state now auto-timeout and cancel if not assigned in time.

- Default timeout: `120s`
- Config key: `INSTANT_MATCH_TIMEOUT_SECONDS`
- Cancel reason set on timeout: `matching_timeout_no_compatible_driver`

### 2.2 Dispatch retry interval configurable

Dispatch re-publish loop interval is now configurable:

- Default retry interval: `10s`
- Config key: `RIDE_DISPATCH_RETRY_SECONDS`

### 2.3 Job lifecycle for instant matching

For instant rides in `matching`:

- Dispatch interval job: `ride_dispatch:{ride_id}`
- Timeout job: `ride_matching_timeout:{ride_id}`

Jobs are cleared when ride leaves `matching` (accepted/canceled/other transition), and rehydrated correctly on app startup.

### 2.4 Scheduled rides behavior

Scheduled rides keep their existing no-driver decision flow and are not auto-canceled by the instant matching timeout logic.

## 3) Vehicle-Type Strictness

### 3.1 Request-time precheck (rider endpoint)

For non-scheduled requests, precheck now verifies **compatible** nearby drivers only.

Compatibility filter includes:

- account status is active
- driver profile complete
- driver presence not stale
- requested vehicle type exactly matches driver vehicle type

If no compatible drivers are found, request fails early with:

- `404`
- `"No compatible drivers available for requested vehicle type within 5km."`

### 3.2 Dispatch-time filtering

Dispatch now uses the same eligibility filter source as precheck, so request-time and publish-time behavior stay aligned.

## 4) Driver Location Update Fix

Driver geo writes no longer use `NX` semantics.

Effect:

- every location update updates the geo index coordinates
- matching uses current driver position instead of the first-ever recorded point

## 5) Rider-Facing Driver Snapshot Payloads

## 5.1 SSE `ride_status_update` (`driverSnapshot`)

`driverSnapshot` now includes:

- `driverId`
- `firstName`
- `lastName`
- `vehicleType`
- `vehicleMake`
- `vehicleModel`
- `vehicleColor`
- `vehiclePlateNumber`
- `vehicleYear`
- `headshotUrl`
- `rating`
- `ratingCount`

Rating defaults for unrated drivers:

- `rating = 0`
- `ratingCount = 0`

## 5.2 Ride polling (`RideOut`)

Ride responses now carry these snapshot fields:

- `driverFirstName`
- `driverLastName`
- `driverVehicleType`
- `driverVehicleMake`
- `driverVehicleModel`
- `driverVehicleColor`
- `driverVehiclePlateNumber`
- `driverVehicleYear`
- `driverHeadshotFileKey`
- `driverHeadshotUrl`
- `driverHeadshotDocumentId`
- `driverRating`
- `driverRatingCount`

These are populated on assignment and enriched on retrieval where needed.

## 6) Key Config Values

- `INSTANT_MATCH_TIMEOUT_SECONDS` (default `120`)
- `RIDE_DISPATCH_RETRY_SECONDS` (default `10`)
- `DRIVER_DISCOVERY_RADIUS_KM` (default `5`)
- `DRIVER_META_TTL_SECONDS` (default `120`)

## 7) Operational Notes

- Instant rides no longer remain in `matching` indefinitely.
- Vehicle mismatch dispatch (e.g., bike request to car-only drivers) is prevented at precheck and dispatch layers.
- Rider trust/visibility is improved through headshot + vehicle + rating exposure in both SSE and polling.

## 8) Example SSE driver snapshot

```json
{
  "driverSnapshot": {
    "driverId": "65f0b9...",
    "firstName": "Alex",
    "lastName": "Morgan",
    "vehicleType": "CAR",
    "vehicleMake": "Toyota",
    "vehicleModel": "Corolla",
    "vehicleColor": "Black",
    "vehiclePlateNumber": "AB12-CDE",
    "vehicleYear": 2018,
    "headshotUrl": "https://...",
    "rating": 4.8,
    "ratingCount": 126
  }
}
```

