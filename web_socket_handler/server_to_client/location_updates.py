# Emits: ride:location_update
from web_socket_handler.base import sio
from web_socket_handler.schemas.messages import DriverLocationUpdate

async def emit_driver_location_update(ride_id: str, driver_id: str, latitude: float, longitude: float, heading: float = None):
    """
    Emit driver location updates to riders in the ride room.

    This should be called periodically when a driver is en route to pickup
    or during the ride to show real-time location to the rider.

    Args:
        ride_id: The ride ID
        driver_id: The driver ID
        latitude: Current latitude
        longitude: Current longitude
        heading: Optional heading/direction in degrees
    """
    try:
        location_update = DriverLocationUpdate(
            driver_id=driver_id,
            latitude=latitude,
            longitude=longitude,
            heading=heading
        )

        await sio.emit("driver_location_update", location_update.model_dump(), room=f"ride_{ride_id}")
        print(f"✅ Emitted driver location update for ride {ride_id}")
    except Exception as e:
        print(f"❌ Failed to emit driver location update for ride {ride_id}: {e}")

async def emit_new_ride_request_to_drivers(ride_request_data):
    """
    Broadcast new ride request to nearby active drivers.

    This should be called when a rider requests a ride to notify
    available drivers in the area.

    Args:
        ride_request_data: NewRideRequest object with ride details
    """
    try:
        # TODO: Implement geospatial query to find nearby drivers
        # For now, broadcast to all active drivers
        await sio.emit("new_ride_request", ride_request_data.model_dump(), room="active_drivers")
        print(f"✅ Broadcasted new ride request {ride_request_data.ride_id} to drivers")
    except Exception as e:
        print(f"❌ Failed to broadcast ride request: {e}")