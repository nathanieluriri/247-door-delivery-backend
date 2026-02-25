from __future__ import annotations

import asyncio
import json
import math
import os
from typing import Any, Literal, Optional, Union

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException

from core.redis_cache import cache_db
from core.vehicles import Vehicle
from schemas.response_schema import APIResponse

load_dotenv()

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
PLACE_BASE_URL = "https://maps.googleapis.com/maps/api/place"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
EARTH_RADIUS_KM = 6371
CACHE_TTL = 14 * 24 * 60 * 60
AUTOCOMPLETE_MIN_LENGTH = 2
AUTOCOMPLETE_DETAILS_CONCURRENCY = 5
PLACE_DETAILS_FIELDS = (
    "place_id,name,formatted_address,geometry,types,rating,user_ratings_total,"
    "icon,formatted_phone_number,website,opening_hours"
)


def _ensure_api_key() -> str:
    if not API_KEY:
        raise HTTPException(status_code=500, detail="Google Maps API key not configured")
    return API_KEY


def _normalize_search_input(input_text: str) -> str:
    return " ".join(input_text.strip().split())


def _map_google_status_to_http(status: str) -> int:
    return {
        "INVALID_REQUEST": 400,
        "OVER_QUERY_LIMIT": 429,
        "REQUEST_DENIED": 403,
    }.get(status, 502)


def _raise_google_error(status: str, error_message: str | None = None) -> None:
    message = error_message or status or "Google Places request failed"
    raise HTTPException(status_code=_map_google_status_to_http(status), detail={"error": message})


def _is_valid_coordinate(latitude: float, longitude: float) -> bool:
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def _autocomplete_cache_key(input_text: str, country: str | None) -> str:
    return f"autocomplete:{country or 'any'}:{input_text.lower()}"


def _reverse_geocode_cache_key(latitude: float, longitude: float, country: str | None) -> str:
    return (
        f"reverse_geocode:{latitude:.6f}:{longitude:.6f}:{(country or 'any').lower()}"
    )


def _build_place_details_cache_key(place_id: str) -> str:
    return f"place_details:{place_id}"


def _result_matches_country(result: dict[str, Any], country: str) -> bool:
    country_code = country.lower()
    for component in result.get("address_components", []):
        if "country" in component.get("types", []) and (
            str(component.get("short_name", "")).lower() == country_code
        ):
            return True
    return False


def _normalize_place_from_geocode(result: dict[str, Any]) -> Optional[dict[str, Any]]:
    place_id = result.get("place_id")
    location = result.get("geometry", {}).get("location", {})
    lat = location.get("lat")
    lng = location.get("lng")
    formatted_address = result.get("formatted_address")

    if not place_id or lat is None or lng is None:
        return None

    title = formatted_address or "Current location"
    return {
        "place_id": place_id,
        "description": title,
        "name": title,
        "address": formatted_address or "",
        "lat": lat,
        "lng": lng,
        "types": result.get("types", []),
    }


async def _enrich_prediction_with_details(
    client: httpx.AsyncClient,
    prediction: dict[str, Any],
    semaphore: asyncio.Semaphore,
    api_key: str,
) -> Optional[dict[str, Any]]:
    place_id = prediction.get("place_id")
    if not place_id:
        return None

    details_params = {
        "place_id": place_id,
        "key": api_key,
        "fields": PLACE_DETAILS_FIELDS,
    }
    async with semaphore:
        details_response = await client.get(f"{PLACE_BASE_URL}/details/json", params=details_params)
        details_data = details_response.json()

    if details_data.get("status") != "OK":
        return None

    result = details_data.get("result", {})
    lat = result.get("geometry", {}).get("location", {}).get("lat")
    lng = result.get("geometry", {}).get("location", {}).get("lng")
    if lat is None or lng is None:
        return None

    description = prediction.get("description")
    if not description:
        description = result.get("formatted_address", "")

    return {
        "place_id": place_id,
        "description": description,
        "name": result.get("name", prediction.get("structured_formatting", {}).get("main_text")),
        "address": result.get("formatted_address", description),
        "lat": lat,
        "lng": lng,
        "types": result.get("types", []),
        "rating": result.get("rating"),
        "user_ratings_total": result.get("user_ratings_total"),
        "icon": result.get("icon"),
    }


async def get_autocomplete(input_text: str, country: str | None = None):
    """Fetch autocomplete suggestions from cache or Google Places API."""
    api_key = _ensure_api_key()
    normalized_input = _normalize_search_input(input_text)
    if len(normalized_input) < AUTOCOMPLETE_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"input must be at least {AUTOCOMPLETE_MIN_LENGTH} characters",
        )

    cache_key = _autocomplete_cache_key(normalized_input, country)
    cached_data = cache_db.get(cache_key)
    if cached_data:
        return APIResponse(
            data=json.loads(cached_data),
            detail="Successfully retrieved place data from cache",
            status_code=200,
        )

    params = {"input": normalized_input, "key": api_key}
    if country:
        params["components"] = f"country:{country}"

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PLACE_BASE_URL}/autocomplete/json", params=params)
        data = response.json()
        status = data.get("status", "")

        if status == "ZERO_RESULTS":
            cache_db.setex(cache_key, CACHE_TTL, json.dumps([]))
            return APIResponse(data=[], detail="No matching places found", status_code=200)

        if status != "OK":
            _raise_google_error(status, data.get("error_message"))

        predictions = data.get("predictions", [])
        if not predictions:
            cache_db.setex(cache_key, CACHE_TTL, json.dumps([]))
            return APIResponse(data=[], detail="No matching places found", status_code=200)

        semaphore = asyncio.Semaphore(AUTOCOMPLETE_DETAILS_CONCURRENCY)
        enrichment_tasks = [
            _enrich_prediction_with_details(client, prediction, semaphore, api_key)
            for prediction in predictions
        ]
        enriched_results = await asyncio.gather(*enrichment_tasks)

    results = [item for item in enriched_results if item is not None]
    cache_db.setex(cache_key, CACHE_TTL, json.dumps(results))

    return APIResponse(data=results, detail="Successfully retrieved place data", status_code=200)


async def get_place_details(place_id: str):
    """Fetch detailed place info from cache or Google Places API."""
    api_key = _ensure_api_key()
    normalized_place_id = place_id.strip()
    if not normalized_place_id:
        raise HTTPException(status_code=400, detail="place_id is required")

    cache_key = _build_place_details_cache_key(normalized_place_id)
    cached_data = cache_db.get(cache_key)
    if cached_data:
        return APIResponse(
            data=json.loads(cached_data),
            detail="Successfully retrieved place data from cache",
            status_code=200,
        )

    params = {
        "place_id": normalized_place_id,
        "key": api_key,
        "fields": PLACE_DETAILS_FIELDS,
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{PLACE_BASE_URL}/details/json", params=params)
        data = response.json()

    status = data.get("status", "")
    if status == "ZERO_RESULTS":
        return APIResponse(data=None, detail="No place details found", status_code=200)
    if status != "OK":
        _raise_google_error(status, data.get("error_message"))

    result = data.get("result", {})
    result_data = {
        "place_id": normalized_place_id,
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

    cache_db.setex(cache_key, CACHE_TTL, json.dumps(result_data))
    return APIResponse(data=result_data, detail="Successfully retrieved place data", status_code=200)


async def get_reverse_geocode(latitude: float, longitude: float, country: str | None = None):
    """Resolve a lat/lng coordinate to a place-like payload including place_id."""
    api_key = _ensure_api_key()
    if not _is_valid_coordinate(latitude, longitude):
        raise HTTPException(status_code=400, detail="Invalid coordinates")

    normalized_country = country.lower() if country else None
    lat_rounded = round(latitude, 6)
    lng_rounded = round(longitude, 6)
    cache_key = _reverse_geocode_cache_key(lat_rounded, lng_rounded, normalized_country)
    cached_data = cache_db.get(cache_key)
    if cached_data:
        return APIResponse(
            data=json.loads(cached_data),
            detail="Successfully retrieved reverse geocode data from cache",
            status_code=200,
        )

    params = {
        "latlng": f"{lat_rounded:.6f},{lng_rounded:.6f}",
        "key": api_key,
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(GEOCODE_URL, params=params)
        data = response.json()

    status = data.get("status", "")
    if status == "ZERO_RESULTS":
        cache_db.setex(cache_key, CACHE_TTL, json.dumps(None))
        return APIResponse(data=None, detail="No matching place found", status_code=200)
    if status != "OK":
        _raise_google_error(status, data.get("error_message"))

    results: list[dict[str, Any]] = data.get("results", [])
    if normalized_country:
        ordered_results = [
            *[result for result in results if _result_matches_country(result, normalized_country)],
            *[result for result in results if not _result_matches_country(result, normalized_country)],
        ]
    else:
        ordered_results = results

    place_data = None
    for result in ordered_results:
        place_data = _normalize_place_from_geocode(result)
        if place_data is not None:
            break

    cache_db.setex(cache_key, CACHE_TTL, json.dumps(place_data))

    if place_data is None:
        return APIResponse(data=None, detail="No matching place found", status_code=200)
    return APIResponse(data=place_data, detail="Successfully reverse geocoded location", status_code=200)


def calculate_fare_using_vehicle_config_and_distance(vehicle: Vehicle, distance: float, time: float) -> float:
    v = vehicle.value
    return v.base_fare + (v.distance_rate * distance) + (v.time_rate * time)


async def nearby_drivers(pickup_lat: float, pickup_lon: float) -> Union[Literal[0], int]:
    try:
        nearby_sids = cache_db.georadius(
            name="drivers:geo_index",
            longitude=pickup_lon,
            latitude=pickup_lat,
            radius=5.0,
            unit="km",
        )

        if not nearby_sids:
            print("⚠️ No drivers found nearby.")
            return 0

        print(f"🔍 Found {len(nearby_sids)} drivers within {5.0}km.")
        return len(nearby_sids)
    except Exception as err:
        print(f"❌ Error broadcasting ride: {err}")
        return 0
