import json
import logging
import math
import os
import time
from typing import Optional, Tuple

from core.redis_cache import async_redis
from core.routing_config import DeliveryRouteResponse, maps
from schemas.imports import RideStatus
from services.place_service import get_place_details
from services.sse_service import get_driver_presence, publish_driver_route_update

logger = logging.getLogger(__name__)

ROUTE_CACHE_TTL_SECONDS = int(os.getenv("DRIVER_ROUTE_CACHE_TTL_SECONDS", "900"))
ROUTE_MIN_INTERVAL_SECONDS = int(os.getenv("DRIVER_ROUTE_MIN_INTERVAL_SECONDS", "30"))
ROUTE_MIN_DISTANCE_METERS = float(os.getenv("DRIVER_ROUTE_MIN_DISTANCE_METERS", "50"))


def _route_cache_key(ride_id: str, status: RideStatus) -> str:
    return f"sse:driver_route:{ride_id}:{status.value}"


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


async def _get_cached_route_meta(ride_id: str, status: RideStatus) -> Optional[dict]:
    payload = await async_redis.get(_route_cache_key(ride_id, status))
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


async def _set_cached_route_meta(ride_id: str, status: RideStatus, meta: dict) -> None:
    await async_redis.setex(
        _route_cache_key(ride_id, status), ROUTE_CACHE_TTL_SECONDS, json.dumps(meta)
    )


async def _should_update_route(
    ride_id: str,
    status: RideStatus,
    driver_lat: float,
    driver_lng: float,
    force: bool,
) -> bool:
    if force:
        return True
    cached = await _get_cached_route_meta(ride_id, status)
    if not cached:
        return True
    last_generated = cached.get("generated_at")
    last_lat = cached.get("driver_lat")
    last_lng = cached.get("driver_lng")
    now = int(time.time())
    try:
        last_generated = int(last_generated)
    except (TypeError, ValueError):
        last_generated = None
    try:
        last_lat = float(last_lat)
        last_lng = float(last_lng)
    except (TypeError, ValueError):
        last_lat = None
        last_lng = None

    if last_generated is None or last_lat is None or last_lng is None:
        return True

    if (now - last_generated) >= ROUTE_MIN_INTERVAL_SECONDS:
        return True

    moved = _haversine_meters(last_lat, last_lng, driver_lat, driver_lng)
    return moved >= ROUTE_MIN_DISTANCE_METERS


async def _resolve_driver_location(driver_id: str) -> Optional[Tuple[float, float]]:
    meta = await get_driver_presence(driver_id)
    if not meta:
        return None
    try:
        lat = float(meta.get("latitude"))
        lng = float(meta.get("longitude"))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return None
    return lat, lng


async def _get_destination_coords(ride) -> Optional[Tuple[float, float]]:
    if not ride.destination:
        return None
    try:
        response = await get_place_details(ride.destination)
    except Exception as exc:
        logger.warning("Failed to resolve destination place id for ride %s: %s", ride.id, exc)
        return None
    data = getattr(response, "data", None) or {}
    lat = data.get("lat")
    lng = data.get("lng")
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lng)):
        return None
    return lat, lng


def _maps_configured() -> bool:
    return maps is not None and getattr(maps, "client", None) is not None


async def _build_route(
    ride,
    status: RideStatus,
    driver_lat: float,
    driver_lng: float,
) -> Tuple[Optional[DeliveryRouteResponse], Optional[str]]:
    if not _maps_configured():
        return None, "Directions API not configured"

    origin = (driver_lat, driver_lng)

    if status == RideStatus.arrivingToPickup:
        if not ride.origin:
            return None, None
        destination = (ride.origin.latitude, ride.origin.longitude)
    elif status == RideStatus.drivingToDestination:
        destination = await _get_destination_coords(ride)
        if not destination:
            return None, None
    else:
        return None, None

    try:
        route = maps.get_delivery_route(origin=origin, destination=destination, stops=[])
    except Exception as exc:
        logger.warning("Failed to generate route for ride %s: %s", ride.id, exc)
        return None, "Unable to generate route"

    if not route:
        return None, "Unable to generate route"

    return route, None


async def maybe_publish_driver_route_for_ride(
    ride,
    status: RideStatus,
    driver_location: Optional[Tuple[float, float]] = None,
    force: bool = False,
) -> None:
    if not ride or not ride.driverId or not ride.userId:
        return

    if status not in {RideStatus.arrivingToPickup, RideStatus.drivingToDestination}:
        return

    if driver_location is None:
        driver_location = await _resolve_driver_location(ride.driverId)

    if not driver_location:
        logger.warning("Driver location missing for ride %s", ride.id)
        return

    driver_lat, driver_lng = driver_location

    if not await _should_update_route(ride.id, status, driver_lat, driver_lng, force):
        return

    route, error = await _build_route(ride, status, driver_lat, driver_lng)
    if error:
        await publish_driver_route_update(
            ride_id=ride.id,
            status=status,
            rider_id=ride.userId,
            driver_id=ride.driverId,
            route=None,
            error=error,
        )
        await _set_cached_route_meta(
            ride.id,
            status,
            {
                "generated_at": int(time.time()),
                "driver_lat": driver_lat,
                "driver_lng": driver_lng,
                "status": status.value,
                "route": None,
                "error": error,
            },
        )
        return

    if not route:
        return

    await publish_driver_route_update(
        ride_id=ride.id,
        status=status,
        rider_id=ride.userId,
        driver_id=ride.driverId,
        route=route,
        error=None,
    )

    await _set_cached_route_meta(
        ride.id,
        status,
        {
            "generated_at": int(time.time()),
            "driver_lat": driver_lat,
            "driver_lng": driver_lng,
            "status": status.value,
            "route": route.model_dump(),
        },
    )
