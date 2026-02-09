# Route Updates (Rider + Driver)

This document describes the SSE route updates sent when a ride transitions out of `findingDriver` and while the driver is en route.

## Rider Route Updates

**Stream**
- `GET /api/v1/sse/rider/stream?ride_id={rideId}&event_types=driver_route_update`

**Event type**
- `driver_route_update`

**When it fires**
- When the ride status changes to `arrivingToPickup`
- When the ride status changes to `drivingToDestination`
- Throttled updates while the driver sends location updates

**Payload**
- `rideId`: string
- `status`: `arrivingToPickup` | `drivingToDestination`
- `generatedAt`: unix timestamp (seconds)
- `route`: object | null
- `error`: string | null

**Route object**
- `totalDistanceMeters`: number
- `totalDurationSeconds`: number
- `encodedPolyline`: string
- `waypointOrder`: number[]
- `legs`: list of `{ startAddress, endAddress, distanceMeters, durationSeconds }`

**Notes**
- If the Directions API is unavailable or no route is returned, `route` is `null` and `error` is populated.
- Use the polyline + duration to render the driver’s path and ETA on the rider UI.

**Examples**
- `GET /api/v1/sse/rider/stream?event_types=driver_route_update`
- `GET /api/v1/sse/rider/stream?ride_id=64f5d1a0b7c0a1e0f2d3c4b5&event_types=driver_route_update`

## Driver Route Updates

**Stream**
- `GET /api/v1/sse/driver/stream?ride_id={rideId}&event_types=driver_route_update`

**Event type**
- `driver_route_update`

**When it fires**
- When the ride status changes to `arrivingToPickup`
- When the ride status changes to `drivingToDestination`
- Throttled updates while the driver sends location updates

**Payload**
- `rideId`: string
- `status`: `arrivingToPickup` | `drivingToDestination`
- `generatedAt`: unix timestamp (seconds)
- `route`: object | null
- `error`: string | null

**Route object**
- `totalDistanceMeters`: number
- `totalDurationSeconds`: number
- `encodedPolyline`: string
- `waypointOrder`: number[]
- `legs`: list of `{ startAddress, endAddress, distanceMeters, durationSeconds }`

**Notes**
- Only the assigned driver receives these events.
- If `error` is set, the client should fall back to local routing or retry later.

**Examples**
- `GET /api/v1/sse/driver/stream?event_types=driver_route_update`
- `GET /api/v1/sse/driver/stream?ride_id=64f5d1a0b7c0a1e0f2d3c4b5&event_types=driver_route_update`
