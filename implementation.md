Plan

1. Define the data contract for driver-to-pickup routing.
- Add a new Pydantic model for a driver route SSE payload (for example: DriverRouteUpdate) that includes rideId, route (encoded polyline plus distance and duration), and generatedAt.
- Add a new SSEEventType value (for example: driver_route_update) and update SSE schema types to include it.
- Decide storage: add driverRoute: Optional[DeliveryRouteResponse] to RideOut and RideUpdate so the route can be fetched later in ride details, while SSE provides realtime updates. (storage should be in cache cause constant driver route update doesn't need persistant storage)

2. Generate route on the status transition.
- Hook into the existing transition findingDriver -> arrivingToPickup in services/ride_service.py (in update_ride_by_id after status update and driver assignment).
- Fetch the driver’s live location from Redis presence (get_driver_presence) and the rider pickup location from ride.origin.
- create a new service for generating encoded polylines for the driver current live location and the rider pickup location and when a ride starts use the driver's current location and the destination location for the new encoded poly lines 


3. Send route updates via SSE.
- Add a publish_driver_route_update(...) helper in services/sse_service.py that sends the route to both rider and driver streams.
- Ensure stream_events() filtering works with the new event type so clients can opt in by event_types.
- Ensure only the driverId and the userId that generated the ride are the receipients of the event to make sure no one else receives these events 

4. Update on live driver location (throttled).
- When drivers post location updates (services/driver_service.py:update_driver_location), if the driver has an active ride in arrivingToPickup, recompute the route to pickup.
- Add throttling and/or distance-change gating (for example: recompute at most every 30 to 60 seconds or after moving N meters) to avoid excessive directions API usage.
- Publish the updated route via SSE and optionally persist the latest route to driverRoute on the ride.

5. Fallbacks and error handling.
- If driver location is missing or stale, or pickup location is missing, skip route generation and log a warning.
- If the Maps API is misconfigured or returns no route, do not block the ride status transition; in the SSE update return the error.

6. Documentation and frontend contract.
- create a new md file talking about the  the new SSE event type and payload fields.
- Note that clients should display the polyline and ETA while the ride is in arrivingToPickup.
