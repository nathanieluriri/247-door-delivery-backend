Driver Route SSE Events

Overview
- A new SSE event type delivers driver-to-pickup and driver-to-destination routing updates for active rides.
- Events are sent only to the rider who created the ride and the assigned driver.

Event Type
- driver_route_update

Payload
- rideId: string
- status: arrivingToPickup | drivingToDestination
- generatedAt: unix timestamp (seconds)
- route: object | null
- error: string | null

Route Object (route)
- totalDistanceMeters: number
- totalDurationSeconds: number
- encodedPolyline: string
- waypointOrder: number[]
- legs: list of objects with startAddress, endAddress, distanceMeters, durationSeconds

Notes
- Updates are throttled and may not be sent on every location tick.
- If the Directions API is unavailable or returns no route, error is populated and route is null.
- Clients should render the polyline and ETA while status is arrivingToPickup or drivingToDestination.
