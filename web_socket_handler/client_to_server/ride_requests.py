# Handles: ride:request, ride:cancel_request
from web_socket_handler.base import sio
from web_socket_handler.utils import handle_accept_logic, handle_complete_logic, handle_start_logic, is_driver, is_rider,handle_cancel_ride_logic
from web_socket_handler.schemas.messages import (
    AcceptRideRequest, AcceptRideResponse,
    StartRideRequest, StartRideResponse,
    CompleteRideRequest, CompleteRideResponse,
    ErrorResponse, RideStatusUpdate
)

@sio.event
async def accept_ride(sid, data):
    """
    Client -> Server: Driver attempts to claim a ride request.
    """
    if not is_driver(sid=sid, require_on_duty=True):
        response = ErrorResponse(message="Unauthorized", detail="This event is for active drivers")
        await sio.emit("accept_ride_response", response.model_dump(), to=sid)
        return

    try:
        req = AcceptRideRequest(**data)
        ride_id = req.ride_id

        # 1. Run Business Logic (DB updates, etc.)
        driver_info = await handle_accept_logic(sid, ride_id)

        if driver_info:
            # 2. Driver joins the communication room
            sio.enter_room(sid, room=f"ride_{ride_id}")

            response = AcceptRideResponse(status="success", message="Ride accepted", driver_info=driver_info)
        else:
            response = AcceptRideResponse(status="error", message="Ride already taken or unavailable")

    except Exception as e:
        print(f"❌ Error in accept_ride: {e}")
        response = AcceptRideResponse(status="error", message="Internal server error")

    await sio.emit("accept_ride_response", response.model_dump(), to=sid)

@sio.event
async def start_ride(sid, data):
    """
    Client -> Server: Driver starts the trip.
    """
    if not is_driver(sid=sid, require_on_duty=True):
        response = ErrorResponse(message="Unauthorized", detail="This event is for active drivers")
        await sio.emit("start_ride_response", response.model_dump(), to=sid)
        return

    try:
        req = StartRideRequest(**data)
        ride_id = req.ride_id

        await handle_start_logic(sid, ride_id)

        response = StartRideResponse(status="success", message="Ride started")

    except Exception as e:
        print(f"❌ Error in start_ride: {e}")
        response = StartRideResponse(status="error", message=str(e))

    await sio.emit("start_ride_response", response.model_dump(), to=sid)

@sio.event
async def cancel_ride(sid, data):
    """
    Client -> Server: Driver cancels.
    """
    try:
        # Assuming data has ride_id and reason
        ride_id = data.get('ride_id')
        reason = data.get('reason', 'Unknown')

        await handle_cancel_ride_logic(sid, ride_id, reason, "DRIVER")

    except Exception as e:
        print(f"❌ Error in cancel_ride: {e}")

@sio.event
async def complete_ride(sid, data):
    """
    Client -> Server: Driver finishes the trip.
    """
    if not is_driver(sid=sid, require_on_duty=True):
        response = ErrorResponse(message="Unauthorized", detail="This event is for active drivers")
        await sio.emit("complete_ride_response", response.model_dump(), to=sid)
        return

    try:
        req = CompleteRideRequest(**data)
        ride_id = req.ride_id

        # Logic returns detail data (fare, etc.)
        result_data = await handle_complete_logic(sid, ride_id)

        # Cleanup
        sio.leave_room(sid, room=f"ride_{ride_id}")

        response = CompleteRideResponse(status="success", message="Ride completed", ride_data=result_data)

    except Exception as e:
        print(f"❌ Error in complete_ride: {e}")
        response = CompleteRideResponse(status="error", message=str(e))

    await sio.emit("complete_ride_response", response.model_dump(), to=sid)