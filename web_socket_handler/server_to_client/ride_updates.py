# Emits: status_change, assigned, driver_arrived
from schemas.imports import RideStatus
from web_socket_handler.schemas.messages import RideStatusUpdate
from web_socket_handler.base import sio

async def emit_ride_status_update(ride_id: str, status: RideStatus, data: dict = None, eta_minutes: int = None):
    """
    Centralized function to emit ride status updates to all participants in the ride room.
    This should be called whenever ride status changes.
    """
    try:
        update = RideStatusUpdate(
            status=status.value,  # Convert enum to string
            data=data,
            eta_minutes=eta_minutes
        )
        await sio.emit("ride_status_update", update.model_dump(), room=f"ride_{ride_id}")
        print(f"✅ Emitted ride status update: {ride_id} -> {status.value}")
    except Exception as e:
        print(f"❌ Failed to emit ride status update for {ride_id}: {e}")

async def emit_ride_assigned(ride_id: str, driver_info: dict, eta_minutes: int = 10):
    """
    Emit ride assigned notification when a driver accepts a ride.
    """
    try:
        data = {
            "driver": driver_info,
            "message": f"Driver {driver_info.get('name', 'assigned')} is on the way!"
        }
        await emit_ride_status_update(ride_id, RideStatus.arrivingToPickup, data, eta_minutes)
    except Exception as e:
        print(f"❌ Failed to emit ride assigned for {ride_id}: {e}")

async def emit_driver_arrived(ride_id: str, driver_info: dict):
    """
    Emit driver arrived notification when driver reaches pickup location.
    """
    try:
        data = {
            "driver": driver_info,
            "message": "Your driver has arrived at the pickup location!"
        }
        await emit_ride_status_update(ride_id, RideStatus.arrivingToPickup, data, 0)
    except Exception as e:
        print(f"❌ Failed to emit driver arrived for {ride_id}: {e}")

async def emit_ride_started(ride_id: str):
    """
    Emit ride started notification when the trip begins.
    """
    try:
        data = {
            "message": "Your ride has started. Enjoy your trip!"
        }
        await emit_ride_status_update(ride_id, RideStatus.drivingToDestination, data, None)
    except Exception as e:
        print(f"❌ Failed to emit ride started for {ride_id}: {e}")

async def emit_ride_completed(ride_id: str, ride_data: dict):
    """
    Emit ride completed notification with final details.
    """
    try:
        data = {
            "ride_data": ride_data,
            "message": "Your ride has been completed. Please rate your driver!"
        }
        await emit_ride_status_update(ride_id, RideStatus.completed, data, 0)
    except Exception as e:
        print(f"❌ Failed to emit ride completed for {ride_id}: {e}")

async def emit_ride_cancelled(ride_id: str, reason: str, cancelled_by: str):
    """
    Emit ride cancelled notification.
    """
    try:
        data = {
            "reason": reason,
            "cancelled_by": cancelled_by,
            "message": f"Ride cancelled: {reason}"
        }
        await emit_ride_status_update(ride_id, RideStatus.canceled, data, None)
    except Exception as e:
        print(f"❌ Failed to emit ride cancelled for {ride_id}: {e}")