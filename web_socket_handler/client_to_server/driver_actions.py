from pydantic import ValidationError
from schemas.place import Location
from web_socket_handler.schemas.drivers import ActiveDrivers
from web_socket_handler.base import sio
from web_socket_handler.utils import is_driver, set_driver_status
from core.redis_cache import cache_db
from web_socket_handler.schemas.messages import (
    GoOnlineRequest, GoOnlineResponse,
    GoOfflineRequest, GoOfflineResponse,
    UpdateLocationRequest, UpdateLocationResponse,
    ErrorResponse
)

@sio.event
async def go_online(sid, data=None):
    """Client -> Server: Mark driver as available."""
    if not is_driver(sid=sid, require_on_duty=False):
        response = ErrorResponse(message="Unauthorized", detail="This event is for drivers")
        await sio.emit("go_online_response", response.model_dump(), to=sid)
        return

    try:
        await set_driver_status(sid, True)
        sio.enter_room(sid, 'active_drivers')
        response = GoOnlineResponse(status="success", message="Driver is now online")
    except Exception as e:
        print(f"Error in go_online: {e}")
        response = GoOnlineResponse(status="error", message="Failed to go online")

    await sio.emit("go_online_response", response.model_dump(), to=sid)

@sio.event
async def go_offline(sid, data=None):
    """Client -> Server: Mark driver as unavailable."""
    if not is_driver(sid=sid, require_on_duty=False):
        response = ErrorResponse(message="Unauthorized", detail="This event is for drivers")
        await sio.emit("go_offline_response", response.model_dump(), to=sid)
        return

    try:
        await set_driver_status(sid, False)
        sio.leave_room(sid, 'active_drivers')
        response = GoOfflineResponse(status="success", message="Driver is now offline")
    except Exception as e:
        print(f"Error in go_offline: {e}")
        response = GoOfflineResponse(status="error", message="Failed to go offline")

    await sio.emit("go_offline_response", response.model_dump(), to=sid)

@sio.event
async def update_location(sid, data):
    """
    Client -> Server event:
    Updates the real-time coordinates of an active driver.

    Expected 'data' payload:
    {
        "latitude": 37.7749,
        "longitude": -122.4194
    }
    """
    if not is_driver(sid=sid, require_on_duty=True):
        response = ErrorResponse(message="Unauthorized", detail="This event is for active drivers")
        await sio.emit("update_location_response", response.model_dump(), to=sid)
        return

    try:
        req = UpdateLocationRequest(**data)
        new_location = Location(latitude=req.latitude, longitude=req.longitude)

        # 2. Find the driver in Redis
        driver = ActiveDrivers.find(ActiveDrivers.sid == sid).first()

        if not driver:
            response = UpdateLocationResponse(status="error", message="Driver not found")
            await sio.emit("update_location_response", response.model_dump(), to=sid)
            return

        # 3. Update the model and save to Redis
        driver.set_coordinates(new_location)
        cache_db.geoadd(
            "drivers:geo_index",
            [req.longitude, req.latitude, sid]
        )
        driver.save()

        response = UpdateLocationResponse(status="success", message="Location updated")

    except ValidationError as e:
        response = UpdateLocationResponse(status="error", message="Invalid data format")
    except Exception as e:
        print(f"❌ Unexpected error in update_location: {e}")
        response = UpdateLocationResponse(status="error", message="Internal error")

    await sio.emit("update_location_response", response.model_dump(), to=sid)