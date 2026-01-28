# SSE Enquiries: Driver Location and Vehicle Type

## Why were `latitude`, `longitude`, and `radius_km` added as query params?

They were added to make the SSE connection self-contained for filtering, but that’s not ideal for fast‑changing location data. Query params are static at connection time, so they quickly go stale. This is fine for “last known” location, but not for live driver tracking.

## Why should `vehicle_type` come from the database instead of query params?

It should. Vehicle type is a stable driver profile attribute. Query params are easy to spoof and can fall out of sync with the actual driver record. Pulling vehicle type from the driver profile ensures the backend is authoritative and prevents mismatch between a driver’s real vehicle and subscription filtering.

## Better approaches (no location in query params)

### 1) **Driver location heartbeat endpoint (recommended)**
Keep SSE for events only, and push location updates via a separate REST endpoint.
- Driver app sends location updates every N seconds (or on significant movement).
- Backend stores last known location in Redis (or DB) with TTL.
- `publish_ride_request` queries the last known location when matching drivers.

Example endpoint:
```
POST /api/v1/drivers/location
Authorization: Bearer <access_token>
{
  "latitude": 6.5244,
  "longitude": 3.3792,
  "accuracy_m": 12,
  "timestamp": 1700000000
}
```

### 2) **WebSocket / bi-directional channel for location**
Use WebSocket for driver telemetry:
- Location updates over the socket.
- SSE remains for server → client only (ride requests, statuses).
- This is more efficient for frequent updates and avoids reconnecting SSE.

### 3) **Redis GEO index for proximity**
On each location update:
- Store driver location in Redis `GEOADD drivers:geo_index driver_id lon lat`.
- On ride creation:
  - Use `GEORADIUS` to get nearby drivers.
  - Filter by vehicle type from driver profile.
  - Then publish SSE only to that subset.

### 4) **Background sync + server‑side matching**
If location updates are frequent:
- Keep a “live location service” that stores all active drivers in Redis.
- SSE subscribers only identify the driver; matching uses server-side live cache.

## Suggested changes to align with the above

- Remove `vehicle_type`, `latitude`, `longitude`, `radius_km` from SSE query params.
- Store `vehicle_type` in driver profile and use it during matching.
- Add a driver location update endpoint (or WebSocket channel).
- Use Redis GEO queries for proximity matching.

## TL;DR

Query params are static and not suited for fast-changing location. Vehicle type should come from the driver profile, not from the client. Use a dedicated location update channel and server-side matching instead.
