# TODO: Emits: status_change, assigned, driver_arrived


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