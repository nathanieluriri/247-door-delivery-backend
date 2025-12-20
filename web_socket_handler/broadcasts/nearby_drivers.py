# TODO: Emits: driver:nearby_update (Geospatial logic)
from core.redis_cache import cache_db
from core.routing_config import Location
from web_socket_handler.base import sio
from web_socket_handler.schemas.messages import NewRideRequest



async def broadcast_ride_request(pickup_lat: float, pickup_lon: float, ride_data: dict, radius_km: float = 5.0):
    """
    Finds drivers within `radius_km` of the pickup point and sends them the request.
    """
    
    try:
        # 1. Use Redis GEORADIUS to find nearby SIDs
        nearby_sids = cache_db.georadius(
            name="drivers:geo_index",
            longitude=pickup_lon,
            latitude=pickup_lat,
            radius=radius_km,
            unit="km"
        )
        
        if not nearby_sids:
            print("⚠️ No drivers found nearby.")
            return 0

        print(f"🔍 Found {len(nearby_sids)} drivers within {radius_km}km.")
        ride_data.get("dropoff").get("lon")
        # Create structured message
        
        request_msg = NewRideRequest(
            ride_id=ride_data["ride_id"],
            pickup={
                "latitude": ride_data["pickup"]["lat"],
                "longitude": ride_data["pickup"]["lon"]
            },
            dropoff={
                "latitude": ride_data["dropoff"]["lat"],
                "longitude": ride_data["dropoff"]["lon"]
            },
            vehicle_type=ride_data["vehicle_type"],
            fare_estimate=ride_data["fare_estimate"]
        )

        # 2. Emit the event ONLY to those specific SIDs
        count = 0
        for sid_raw in nearby_sids:
            if isinstance(sid_raw, bytes):
                sid = sid_raw.decode('utf-8')
            else:
                sid = sid_raw
            
            await sio.emit("new_ride_request", request_msg.model_dump(), to=sid)
            count += 1
            
        print(f"✅ Request sent to {count} drivers.")
        return count

    except Exception as e:
        print(f"❌ Error broadcasting ride: {e}")
        return 0