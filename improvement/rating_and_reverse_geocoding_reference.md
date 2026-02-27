# Rating and Reverse Geocoding Reference

## Summary
This document explains:

1. How rider/driver rating works (write flow + read/aggregation flow).
2. How rating is exposed in ride polling and SSE driver snapshots.
3. How reverse geocoding works (validation, caching, country preference, fallback behavior).

---

## 1) Rating: Data Model and Validation

Schema source: `schemas/rating.py`

- `RatingBase`
  - `rideId: str`
  - `userId: str` (the user being rated)
  - `rating: int` (must be between `1` and `5`)
- `RatingCreate`
  - all `RatingBase` fields
  - `raterId: str` (the actor who gave the rating)
  - timestamps: `date_created`, `last_updated`
- `RatingSummary`
  - `avgRating: float`
  - `totalRides: int`

Important:
- Rating value is strictly integer `1..5`.
- `userId` is the target user, not the authenticated caller.

---

## 2) Rating: Write Rules

Service source: `services/rating_service.py` (`add_rating`)

Before a rating is saved:
1. Ride is fetched using `rideId`.
2. Ride must be in one of these statuses:
   - `completed`
   - `awaitingPayment`
   - `paymentFailed`
3. Caller context must match ride ownership:
   - Driver rating flow: `ride.driverId == driverId`
   - Rider rating flow: `ride.userId == riderId`

Failure behavior:
- Unauthorized actor/ride mismatch -> `403`
- Missing actor context (`driverId` and `riderId` both missing) -> `400`

---

## 3) Rating Endpoints

### Driver routes

- `GET /api/v1/drivers/rating`
  - Returns authenticated driver rating summary.
- `GET /api/v1/drivers/rider/{riderId}/rating`
  - Returns any rider's summary by rider ID.
- `POST /api/v1/drivers/rate/rider`
  - Body: `RatingBase`
  - Backend adds `raterId` from token and calls rating service with `driverId`.

Example body:
```json
{
  "rideId": "ride_123",
  "userId": "rider_user_id",
  "rating": 5
}
```

### Rider routes

- `GET /api/v1/riders/rating`
  - Returns authenticated rider rating summary.
- `GET /api/v1/riders/driver/{driverId}/rating`
  - Returns any driver's summary by driver ID.
- `POST /api/v1/riders/rate/driver`
  - Body: `RatingBase`
  - Backend adds `raterId` from token and creates a rating record.

Note:
- The service enforces actor context through `driverId`/`riderId` arguments.
- If rider flow does not pass rider context into service call, service returns `400`.

---

## 4) Rating Aggregation (Summary)

Repository source: `repositories/rating.py` (`get_user_rating_summary`)

Aggregation pipeline:
- Match ratings by `userId` (rated user).
- Group to compute:
  - `avgRating = average(rating)`
  - `totalRides = count(*)`

No ratings behavior:
- Returns:
```json
{
  "avgRating": 0,
  "totalRides": 0
}
```

---

## 5) Rating in Ride Polling and SSE

Driver snapshot builder source: `services/driver_snapshot_service.py`

When driver snapshot is built:
- `driverRating` <- `avgRating`
- `driverRatingCount` <- `totalRides`

### Ride polling (`RideOut`)
Ride payload includes:
- `driverRating`
- `driverRatingCount`

Schema source: `schemas/ride.py`

### Rider SSE `ride_status_update.driverSnapshot`
SSE payload includes:
- `rating`
- `ratingCount`

Schema source: `schemas/sse.py` (`DriverSnapshot`)

Mapping:
- `driverRating` -> `driverSnapshot.rating`
- `driverRatingCount` -> `driverSnapshot.ratingCount`

---

## 6) Reverse Geocoding (Reverse Geo Encoding) Flow

Route source: `api/v1/rider_route.py`
- Endpoint: `GET /api/v1/riders/place/reverse-geocode`
- Query:
  - `lat` (required, `-90..90`)
  - `lng` (required, `-180..180`)
  - `country` (optional; allowed: `us|ng|uk|ca|de|fr|au|jp`)

Service source: `services/place_service.py` (`get_reverse_geocode`)

### Step-by-step

1. Validate coordinates (`_is_valid_coordinate`).
2. Normalize:
   - country lowercased
   - lat/lng rounded to 6 decimals
3. Check Redis cache key:
   - `reverse_geocode:{lat:.6f}:{lng:.6f}:{country_or_any}`
4. If cache miss, call Google Geocoding API:
   - `https://maps.googleapis.com/maps/api/geocode/json`
   - with `latlng` and API key
5. Handle upstream status:
   - `ZERO_RESULTS` -> cache `null`, return `data: null` with 200
   - non-`OK` -> mapped HTTP errors:
     - `INVALID_REQUEST` -> 400
     - `OVER_QUERY_LIMIT` -> 429
     - `REQUEST_DENIED` -> 403
     - anything else -> 502
6. If `country` is provided:
   - Results are reordered to prefer matching country first.
   - It still falls back to non-matching results if needed.
7. First usable result is normalized to a place-like payload:
   - `place_id`
   - `description`
   - `name`
   - `address`
   - `lat`
   - `lng`
   - `types`
8. Response is cached for 14 days (`CACHE_TTL = 1209600` seconds).

### Success response shape
```json
{
  "status_code": 200,
  "detail": "Successfully reverse geocoded location",
  "data": {
    "place_id": "ChI...",
    "description": "221B Baker Street, London NW1 6XE, UK",
    "name": "221B Baker Street, London NW1 6XE, UK",
    "address": "221B Baker Street, London NW1 6XE, UK",
    "lat": 51.523767,
    "lng": -0.158555,
    "types": ["street_address"]
  }
}
```

### No result response shape
```json
{
  "status_code": 200,
  "detail": "No matching place found",
  "data": null
}
```

---

## 7) Frontend Handling Guidance

For rating:
- Use `GET /rating` endpoints to render profile rating summary.
- Use ride payload (`driverRating`, `driverRatingCount`) or SSE driver snapshot (`rating`, `ratingCount`) for trip-time display.

For reverse geocoding:
- Treat `data: null` as a valid no-result state.
- Fallback UX: prompt user to search with `/place/autocomplete`.
- Avoid sending unstable/high-precision noisy coordinates repeatedly; cache already rounds to 6 decimals.
