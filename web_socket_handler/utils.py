import math
from repositories.tokens_repo import get_access_tokens, get_access_tokens_no_date_check
from schemas.imports import RideStatus
from schemas.ride import RideUpdate
from security.encrypting_jwt import JWTPayload, decode_jwt_token
from services.driver_service import retrieve_driver_by_driver_id
from services.rating_service import retrieve_rating_by_user_id
from services.ride_service import update_ride_by_id
from web_socket_handler.schemas.drivers import ActiveDrivers
from web_socket_handler.schemas.imports import *
from redis_om import NotFoundError
from core.routing_config import maps
from web_socket_handler.schemas.riders import ActiveRiders
from web_socket_handler.server_to_client.ride_updates import emit_ride_status_update
from web_socket_handler.schemas.messages import RideStatusUpdate



def sync_save_active_user(sid, user_id, user_type):
    """
    Synchronously saves the user to Redis and sets the TTL.
    This runs in a separate thread to avoid blocking the main loop.
    """
    try:
        if user_type == "DRIVER":
            driver = ActiveDrivers(sid=sid, user_id=user_id).save()
             
            print(f"✅ Driver saved to Redis: {sid}")
            
        elif user_type == "RIDER":
            rider = ActiveRiders(sid=sid, user_id=user_id).save()
            
            print(f"✅ Rider saved to Redis: {sid}")
            
    except Exception as e:
        # Crucial: Catch errors here so a DB failure doesn't crash the thread quietly
        print(f"❌ Error saving user to Redis: {e}")

def sync_cleanup_user(sid):
    # ----------------------------------------
    # 1. Try to find/delete a RIDER
    # ----------------------------------------
    try:
        rider = ActiveRiders.find(ActiveRiders.sid == sid).first()
        ActiveRiders.delete(rider.pk)
        print(f"Cleaned up Rider: {sid}")
        return # We found them, so we can stop here
    except NotFoundError:
        pass # Not a Rider? Ignore the error and continue to check Drivers.

    # ----------------------------------------
    # 2. Try to find/delete a DRIVER
    # ----------------------------------------
    try:
        driver = ActiveDrivers.find(ActiveDrivers.sid == sid).first()
        ActiveDrivers.delete(driver.pk)
        print(f"Cleaned up Driver: {sid}")
    except NotFoundError:
        # If we get here, the sid wasn't in EITHER table.
        # This is normal if their session expired (TTL) before they disconnected.
        print(f"Sid {sid} not found in DB (already expired or never existed).")
        
    try:
        cache_db.zrem("drivers:geo_index", sid)
    except:
        pass
        
async def websocket_authorization_func(environ)-> Union[ SmallUserObject, None]:
    # This is deprecated, auth now handled via 'authenticate' event
    return None
    
    
    


def distance_km(pickup:Location, dropoff:Location) -> int:
    distance  = maps.calculate_road_distance(start_location=pickup,stop_location=dropoff)
    return distance



async def set_driver_status(sid: str, is_active: bool):
    """
    Helper function to toggle driver status to avoid repeating code.
    """
    print("i'm here now")
    try:
        # 1. Find driver
        driver = ActiveDrivers.find(ActiveDrivers.sid == sid).first()
        if not driver:
            print(f"❌ Driver with SID {sid} not found")
         
            return

        # 2. Update status
        # driver.is_active = is_active
        driver.set_active(is_active)
        driver.save()
        
        status_str = "online" if is_active else "offline"
        print(f"✅ Driver {driver.user_id} is now {status_str}")

        # 3. Notify driver
        

    except Exception as e:
        print(f"❌ Error setting driver {status_str}: {e}")
         



def is_rider(sid: str) -> bool:
    """
    Checks if the given SID belongs to a connected Rider.
    Returns True if found in ActiveRiders, False otherwise.
    """
    from web_socket_handler.base import authenticated_users
    user = authenticated_users.get(sid)
    if user and user['user_type'] == 'RIDER':
        try:
            rider = ActiveRiders.find(ActiveRiders.sid == sid).first()
            return True if rider else False
        except Exception as e:
            print(f"⚠️ Error checking Rider role for {sid}: {e}")
            return False
    return False

def is_driver(sid: str, require_on_duty: bool = False) -> bool:
    """
    Checks if the given SID belongs to a connected Driver.
    
    Args:
        sid: The socket ID to check.
        require_on_duty: If True, also checks if driver.is_active == 1.
                         If False (default), just checks if they are connected/logged in.
    """
    from web_socket_handler.base import authenticated_users
    user = authenticated_users.get(sid)
    if user and user['user_type'] == 'DRIVER':
        try:
            driver = ActiveDrivers.find(ActiveDrivers.sid == sid).first()
            
            if not driver:
                return False
                
            if require_on_duty:
                # Check the boolean flag (stored as int 0 or 1)
                return driver.is_driver_active()
                
            return True

        except Exception as e:
            print(f"⚠️ Error checking Driver role for {sid}: {e}")
            return False
    return False
    
    
    
    
async def handle_accept_logic(sid,ride_id):
    driver = ActiveDrivers.find(ActiveDrivers.sid == sid).first()
    ride_data = RideUpdate(driverId=driver.user_id,rideStatus=RideStatus.arrivingToPickup)
    await update_ride_by_id(ride_id=ride_id,driver_id=driver.user_id,ride_data=ride_data)
    driver_info = await retrieve_driver_by_driver_id(id=driver.user_id)
    d =driver_info.model_dump()
    ratings = await retrieve_rating_by_user_id(user_id=driver_info.id)
    d["Ratings"]= ratings.model_dump()

    # Emit status update with driver assignment
    from web_socket_handler.server_to_client.ride_updates import emit_ride_assigned
    await emit_ride_assigned(ride_id, d, 10)

    return d



async def handle_start_logic(sid,ride_id):
    driver = ActiveDrivers.find(ActiveDrivers.sid == sid).first()
    ride_data = RideUpdate(driverId=driver.user_id,rideStatus=RideStatus.drivingToDestination)
    await update_ride_by_id(ride_id=ride_id,driver_id=driver.user_id,ride_data=ride_data)

    # Emit ride started update
    from web_socket_handler.server_to_client.ride_updates import emit_ride_started
    await emit_ride_started(ride_id) 
    
    
    
async def handle_complete_logic(sid,ride_id):
    driver = ActiveDrivers.find(ActiveDrivers.sid == sid).first()
    ride_data = RideUpdate(driverId=driver.user_id,rideStatus=RideStatus.completed)
    ride = await update_ride_by_id(ride_id=ride_id,driver_id=driver.user_id,ride_data=ride_data)

    # Emit ride completed update
    from web_socket_handler.server_to_client.ride_updates import emit_ride_completed
    await emit_ride_completed(ride_id, ride.model_dump())

    return ride.model_dump()

async def handle_cancel_ride_logic(sid, ride_id, reason, cancelled_by):
    """
    Handle ride cancellation logic for both riders and drivers.
    """
    # Determine who is cancelling
    if is_driver(sid):
        user_type = "DRIVER"
        driver = ActiveDrivers.find(ActiveDrivers.sid == sid).first()
        user_id = driver.user_id
    elif is_rider(sid):
        user_type = "RIDER"
        rider = ActiveRiders.find(ActiveRiders.sid == sid).first()
        user_id = rider.user_id
    else:
        raise ValueError("Unauthorized user attempting to cancel ride")

    # Update ride status
    ride_update = RideUpdate(rideStatus=RideStatus.canceled)
    await update_ride_by_id(
        ride_id=ride_id,
        ride_data=ride_update,
        rider_id=user_id if user_type == "RIDER" else None,
        driver_id=user_id if user_type == "DRIVER" else None
    )

 
    # Emit cancellation update
    from web_socket_handler.server_to_client.ride_updates import emit_ride_cancelled
    await emit_ride_cancelled(ride_id, reason, user_type)
    