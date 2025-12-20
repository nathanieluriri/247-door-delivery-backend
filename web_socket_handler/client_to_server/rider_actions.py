from pydantic import ValidationError
from schemas.place import Location
from services.ride_service import retrieve_rides_by_user_id_and_ride_id
from web_socket_handler.schemas.drivers import ActiveDrivers
from web_socket_handler.base import sio
from web_socket_handler.schemas.riders import ActiveRiders
from web_socket_handler.utils import is_rider
from core.redis_cache import cache_db
from web_socket_handler.schemas.messages import (
    JoinRideRoomRequest, JoinRideRoomResponse,
    GetRideStateRequest, GetRideStateResponse,
    ErrorResponse
)

@sio.event
async def join_ride_room(sid, data):
    """
    Client -> Server: Rider joins the room after creating a ride via HTTP.
    """
    if not is_rider(sid=sid):
        response = ErrorResponse(message="Unauthorized", detail="This event is for riders")
        await sio.emit("join_ride_room_response", response.model_dump(), to=sid)
        return

    try:
        req = JoinRideRoomRequest(**data)
        ride_id = req.ride_id

        rider = ActiveRiders.find(ActiveRiders.sid == sid).first()
        ride = await retrieve_rides_by_user_id_and_ride_id(user_id=rider.user_id, ride_id=ride_id)
        sio.enter_room(sid, f"ride_{ride.id}")
        print(f"✅ User {sid} joined room ride_{ride_id}")
        response = JoinRideRoomResponse(status="success", message="Joined ride room", ride_data=ride.model_dump())
    except Exception as e:
        print(f"No ride was found: {e}")
        response = JoinRideRoomResponse(status="error", message="Ride not found")

    await sio.emit("join_ride_room_response", response.model_dump(), to=sid)

@sio.event
async def get_ride_state(sid, data):
    """
    Client -> Server: "I just reconnected, give me the full update."
    Expected data: { "ride_id": "12345" }
    """
    if not is_rider(sid=sid):
        response = ErrorResponse(message="Unauthorized", detail="This event is for riders")
        
        await sio.emit("get_ride_state_response", response.model_dump(), to=sid)
        return

    try:
        req = GetRideStateRequest(**data)
        ride_id = req.ride_id

        # 1. Re-join the room (Safety net in case they lost connection)
        sio.enter_room(sid, f"ride_{ride_id}")

        # 2. Fetch the snapshot
        rider = ActiveRiders.find(ActiveRiders.sid == sid).first()
        ride = await retrieve_rides_by_user_id_and_ride_id(user_id=rider.user_id, ride_id=ride_id)

        if not ride:
            response = GetRideStateResponse(status="error", message="Ride not found")
        else:
            response = GetRideStateResponse(status="success", message="Ride state retrieved", ride_data=ride.model_dump())

    except Exception as e:
        print(f"❌ Error syncing state: {e}")
        response = GetRideStateResponse(status="error", message="Internal error")

    await sio.emit("get_ride_state_response", response.model_dump(), to=sid)
    print("after last emission ",response)