# ============================================================================
# PLACE SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-04 00:56:13 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================
from typing import Literal, Union
import httpx
import os
import json
import redis
from dotenv import load_dotenv
from core.redis_cache import cache_db
from core.vehicles import Vehicle
from schemas.response_schema import APIResponse
from fastapi import HTTPException
import math
load_dotenv()

# Google API setup
API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
BASE_URL = "https://maps.googleapis.com/maps/api/place"
EARTH_RADIUS_KM = 6371
 

# Cache TTL: 14 days in seconds
CACHE_TTL = 14 * 24 * 60 * 60  # 1209600 seconds


async def get_autocomplete(input_text: str, country: str | None = None):
    """Fetch autocomplete suggestions from cache or Google Places API."""
    cache_key = f"autocomplete:{country or 'any'}:{input_text.lower().strip()}"

    # ✅ Check cache first
    cached_data = cache_db.get(cache_key)
    if cached_data:
        results = json.loads(cached_data)
        return APIResponse(
            data=results,
            detail="Successfully retrieved place data from cache",
            status_code=200
        )

    # 🔍 Not in cache — fetch from Google Places Autocomplete API
    params = {"input": input_text, "key": API_KEY}
    if country:
        params["components"] = f"country:{country}"

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/autocomplete/json", params=params)
        data = response.json()

    if data.get("status") != "OK":
        raise HTTPException(
            status_code=500,
            detail={"error": data.get("error_message", data.get("status"))}
        )

    predictions = data.get("predictions", [])
    results = []

    # 🔍 Get details for each place to enrich with lat/lng, name, etc.
    async with httpx.AsyncClient() as client:
        for p in predictions:
            place_id = p["place_id"]

            # Fetch details for each autocomplete result
            details_params = {"place_id": place_id, "key": API_KEY}
            details_response = await client.get(f"{BASE_URL}/details/json", params=details_params)
            details_data = details_response.json()

            if details_data.get("status") != "OK":
                continue

            result = details_data.get("result", {})

            enriched_place = {
                "place_id": place_id,
                "description": p["description"],
                "name": result.get("name", p.get("structured_formatting", {}).get("main_text")),
                "address": result.get("formatted_address", p["description"]),
                "lat": result.get("geometry", {}).get("location", {}).get("lat"),
                "lng": result.get("geometry", {}).get("location", {}).get("lng"),
                "types": result.get("types", []),
                "rating": result.get("rating"),
                "user_ratings_total": result.get("user_ratings_total"),
                "icon": result.get("icon"),
            }
            results.append(enriched_place)

    # 💾 Store in Redis (cache enriched results)
    cache_db.setex(cache_key, CACHE_TTL, json.dumps(results))

    return APIResponse(
        data=results,
        detail="Successfully retrieved place data",
        status_code=200
    )


async def get_place_details(place_id: str):
    """Fetch detailed place info from cache or Google Places API."""
    cache_key = f"place_details:{place_id}"

    # ✅ Check cache first
    cached_data = cache_db.get(cache_key)
    if cached_data:
        result_data = json.loads(cached_data)
        return APIResponse(
            data=result_data,
            detail="Successfully retrieved place data from cache",
            status_code=200
        )

    # 🔍 Not in cache — fetch from Google
    params = {"place_id": place_id, "key": API_KEY}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/details/json", params=params)
        data = response.json()

    if data.get("status") != "OK":
        raise HTTPException(
            status_code=500,
            detail={"error": data.get("error_message", data.get("status"))}
        )

    result = data.get("result", {})

    result_data = {
        "place_id": place_id,
        "name": result.get("name"),
        "address": result.get("formatted_address"),
        "lat": result.get("geometry", {}).get("location", {}).get("lat"),
        "lng": result.get("geometry", {}).get("location", {}).get("lng"),
        "phone_number": result.get("formatted_phone_number"),
        "website": result.get("website"),
        "types": result.get("types", []),
        "rating": result.get("rating"),
        "user_ratings_total": result.get("user_ratings_total"),
        "icon": result.get("icon"),
        "opening_hours": result.get("opening_hours", {}).get("weekday_text"),
    }

    # 💾 Cache result
    cache_db.setex(cache_key, CACHE_TTL, json.dumps(result_data))

    return APIResponse(
        data=result_data,
        detail="Successfully retrieved place data",
        status_code=200
    )



async def get_place_details(place_id: str):
    """Fetch detailed place info from cache or Google Places API."""
    cache_key = f"place_details:{place_id}"

    # ✅ Check cache first
    cached_data = cache_db.get(cache_key)
    if cached_data:
        result_data= json.loads(cached_data)
        response = APIResponse(data=result_data,detail="Successfully retrieved place data from cache",status_code=200)
        return response

    # 🔍 Not in cache — fetch from Google
    params = {"place_id": place_id, "key": API_KEY}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/details/json", params=params)
        data = response.json()

    if data.get("status") != "OK":
        raise HTTPException(status_code=500,detail={"error": data.get("error_message", data.get("status"))}) 

    result = data.get("result",None)
 
     
    result_data = {
        "name": result.get("name",None),
        "address": result.get("formatted_address",None),
        "lat": result.get('geometry', {}).get('location', {}).get('lat'),
        "lng": result.get('geometry', {}).get('location', {}).get('lng'),
    }
    

    # 💾 Store in Redis
    cache_db.setex(cache_key, CACHE_TTL, json.dumps(result_data))
    response = APIResponse(data=result_data,detail="Successfully retrieved place data",status_code=200)
    return response


 


def calculate_fare_using_vehicle_config_and_distance(vehicle: Vehicle, distance: float, time: float) -> float:
    
    v = vehicle.value
    
    return (v.base_fare + (v.distance_rate * distance) + (v.time_rate * time))






async def nearby_drivers(pickup_lat:float,pickup_lon:float)->Union[Literal[0],int]:
    try:
        # 1. Use Redis GEORADIUS to find nearby SIDs
        nearby_sids = cache_db.georadius(
            name="drivers:geo_index",
            longitude=pickup_lon,
            latitude=pickup_lat,
            radius= 5.0,
            unit="km"
        )
        
        if not nearby_sids:
            print("⚠️ No drivers found nearby.")
            return 0

        print(f"🔍 Found {len(nearby_sids)} drivers within { 5.0}km.")
        return len(nearby_sids)
    except Exception as e:
        print(f"❌ Error broadcasting ride: {e}")
        return 0