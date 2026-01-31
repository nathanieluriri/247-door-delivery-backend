import asyncio
import os
import time
import uuid
from typing import Iterable, Optional

from fastapi import Request
from pydantic import BaseModel

from core.redis_cache import async_redis
from schemas.sse import SSEEvent, RideStatusUpdate, ChatMessageEvent, RideRequestEvent


RETRY_AFTER_SECONDS = int(os.getenv("SSE_RETRY_AFTER_SECONDS", "5"))
EVENT_TTL_SECONDS = int(os.getenv("SSE_EVENT_TTL_SECONDS", "86400"))
POLL_INTERVAL_SECONDS = float(os.getenv("SSE_POLL_INTERVAL_SECONDS", "1"))
DRIVER_DISCOVERY_RADIUS_KM = float(os.getenv("DRIVER_DISCOVERY_RADIUS_KM", "5"))
DRIVER_META_TTL_SECONDS = int(os.getenv("DRIVER_META_TTL_SECONDS", "120"))
DRIVER_GEO_INDEX = os.getenv("DRIVER_GEO_INDEX", "drivers:geo_index")


def _pending_key(user_type: str, user_id: str) -> str:
    return f"sse:pending:{user_type}:{user_id}"


def _event_key(event_id: str) -> str:
    return f"sse:event:{event_id}"


def _subscribers_key(user_type: str) -> str:
    return f"sse:subscribers:{user_type}"


def _driver_presence_key(driver_id: str) -> str:
    return f"sse:driver_presence:{driver_id}"


def _active_session_key(user_type: str, user_id: str) -> str:
    return f"sse:session:{user_type}:{user_id}"


def _format_sse(event: SSEEvent) -> str:
    payload = event.model_dump_json(by_alias=True)
    return f"id: {event.id}\nevent: {event.event}\ndata: {payload}\n\n"


async def register_subscriber(user_type: str, user_id: str) -> None:
    await async_redis.sadd(_subscribers_key(user_type), user_id)


async def unregister_subscriber(user_type: str, user_id: str) -> None:
    await async_redis.srem(_subscribers_key(user_type), user_id)


async def get_subscribers(user_type: str) -> Iterable[str]:
    return await async_redis.smembers(_subscribers_key(user_type))


async def set_driver_presence(driver_id: str, meta: dict) -> None:
    if not meta:
        return
    meta_key = _driver_presence_key(driver_id)
    await async_redis.hset(meta_key, mapping=meta)
    await async_redis.expire(meta_key, DRIVER_META_TTL_SECONDS)


async def get_driver_presence(driver_id: str) -> dict:
    meta_key = _driver_presence_key(driver_id)
    return await async_redis.hgetall(meta_key)


async def delete_driver_presence(driver_id: str) -> None:
    meta_key = _driver_presence_key(driver_id)
    await async_redis.delete(meta_key)


def _normalize_vehicle_type(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().upper()
    if "." in normalized:
        normalized = normalized.split(".")[-1]
    return normalized


async def update_driver_presence(
    driver_id: str,
    latitude: float,
    longitude: float,
    vehicle_type: Optional[str],
    profile_complete: bool = False,
    timestamp: Optional[int] = None,
    account_status: Optional[str] = None,
) -> None:
    now = int(time.time()) if timestamp is None else int(timestamp)
    await async_redis.geoadd(DRIVER_GEO_INDEX, {driver_id: (longitude, latitude)})
    await set_driver_presence(
        driver_id,
        {
            "vehicle_type": _normalize_vehicle_type(vehicle_type),
            "latitude": latitude,
            "longitude": longitude,
            "last_seen": now,
            "profile_complete": "1" if profile_complete else "0",
            "account_status": (account_status or "").lower(),
        },
    )



async def publish_event(
    user_type: str,
    user_id: str,
    event_type: str,
    data: BaseModel | dict,
) -> SSEEvent:
    event_id = uuid.uuid4().hex
    payload = data.model_dump(by_alias=True) if isinstance(data, BaseModel) else data
    event = SSEEvent(
        id=event_id,
        event=event_type,
        data=payload,
        created_at=int(time.time()),
    )

    event_key = _event_key(event_id)
    pending_key = _pending_key(user_type, user_id)
    pipe = async_redis.pipeline()
    pipe.hset(
        event_key,
        mapping={
            "payload": event.model_dump_json(by_alias=True),
            "user_type": user_type,
            "user_id": user_id,
            "event_type": event_type,
            "created_at": str(event.created_at),
            "last_sent_at": "0",
        },
    )
    pipe.expire(event_key, EVENT_TTL_SECONDS)
    pipe.rpush(pending_key, event_id)
    await pipe.execute()
    return event


async def ack_event(user_type: str, user_id: str, event_id: str) -> bool:
    event_key = _event_key(event_id)
    record = await async_redis.hgetall(event_key)
    if not record:
        return False
    if record.get("user_type") != user_type or record.get("user_id") != user_id:
        return False

    pipe = async_redis.pipeline()
    pipe.lrem(_pending_key(user_type, user_id), 0, event_id)
    pipe.delete(event_key)
    await pipe.execute()
    return True


async def stream_events(
    request: Request,
    user_type: str,
    user_id: str,
    event_types: Optional[Iterable[str]] = None,
    ride_id: Optional[str] = None,
):
    await register_subscriber(user_type, user_id)
    session_id = None
    active_key = None
    if user_type == "driver":
        session_id = uuid.uuid4().hex
        active_key = _active_session_key(user_type, user_id)
        await async_redis.set(active_key, session_id, ex=EVENT_TTL_SECONDS)

    pending_key = _pending_key(user_type, user_id)
    allowed_types = set(event_types) if event_types else None

    try:
        while True:
            if await request.is_disconnected():
                break
            if session_id and active_key:
                current_session = await async_redis.get(active_key)
                if current_session != session_id:
                    break
                await async_redis.expire(active_key, EVENT_TTL_SECONDS)

            now = int(time.time())
            pending_ids = await async_redis.lrange(pending_key, 0, -1)
            sent_any = False

            for event_id in pending_ids:
                event_key = _event_key(event_id)
                record = await async_redis.hgetall(event_key)
                if not record:
                    await async_redis.lrem(pending_key, 0, event_id)
                    continue

                if record.get("user_type") != user_type or record.get("user_id") != user_id:
                    continue

                last_sent_at = int(float(record.get("last_sent_at") or 0))
                if now - last_sent_at < RETRY_AFTER_SECONDS:
                    continue

                payload = record.get("payload")
                if not payload:
                    await async_redis.lrem(pending_key, 0, event_id)
                    await async_redis.delete(event_key)
                    continue

                event = SSEEvent.model_validate_json(payload)
                if allowed_types and event.event not in allowed_types:
                    continue
                if ride_id:
                    event_ride_id = event.data.get("ride_id") or event.data.get("rideId")
                    if event_ride_id != ride_id:
                        continue

                await async_redis.hset(event_key, "last_sent_at", str(now))
                sent_any = True
                yield _format_sse(event)

            if not sent_any:
                yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    finally:
        if session_id and active_key:
            current_session = await async_redis.get(active_key)
            if current_session == session_id:
                await async_redis.delete(active_key)
                await delete_driver_presence(user_id)
                await unregister_subscriber(user_type, user_id)
        else:
            await unregister_subscriber(user_type, user_id)


async def publish_ride_status_update(
    ride_id: str,
    status,
    rider_id: Optional[str],
    driver_id: Optional[str],
    message: Optional[str] = None,
    eta_minutes: Optional[int] = None,
) -> None:
    payload = RideStatusUpdate(
        rideId=ride_id,
        status=status,
        message=message,
        etaMinutes=eta_minutes,
    )
    if rider_id:
        await publish_event("rider", rider_id, "ride_status_update", payload)
    if driver_id:
        await publish_event("driver", driver_id, "ride_status_update", payload)


async def publish_chat_message(
    chat_id: str,
    ride_id: str,
    sender_id: str,
    sender_type,
    message: str,
    timestamp: int,
    rider_id: Optional[str],
    driver_id: Optional[str],
) -> None:
    payload = ChatMessageEvent(
        chatId=chat_id,
        rideId=ride_id,
        senderId=sender_id,
        senderType=sender_type,
        message=message,
        timestamp=timestamp,
    )
    if rider_id:
        await publish_event("rider", rider_id, "chat_message", payload)
    if driver_id:
        await publish_event("driver", driver_id, "chat_message", payload)


async def publish_ride_request_to_drivers(
    payload: RideRequestEvent,
    pickup_location: Optional[tuple[float, float]] = None,
) -> int:
    pickup_lat = None
    pickup_lng = None
    if pickup_location:
        pickup_lat, pickup_lng = pickup_location

    if pickup_lat is None or pickup_lng is None:
        return 0

    requested_vehicle = _normalize_vehicle_type(payload.vehicle_type)
    count = 0
    driver_ids = await async_redis.georadius(
        name=DRIVER_GEO_INDEX,
        longitude=pickup_lng,
        latitude=pickup_lat,
        radius=DRIVER_DISCOVERY_RADIUS_KM,
        unit="km",
    )
    for driver_id in driver_ids:
        meta = await get_driver_presence(driver_id)
        if not meta:
            continue
        if meta.get("account_status") not in {"active"}:
            continue

        if meta.get("profile_complete") not in {"1", "true", "True", "TRUE"}:
            continue

        driver_vehicle = _normalize_vehicle_type(meta.get("vehicle_type"))
        if requested_vehicle and driver_vehicle and driver_vehicle != requested_vehicle:
            continue

        if requested_vehicle and not driver_vehicle:
            continue

        driver_lat = meta.get("latitude")
        driver_lng = meta.get("longitude")
        if pickup_lat is None or pickup_lng is None or driver_lat is None or driver_lng is None:
            continue

        try:
            driver_lat = float(driver_lat)
            driver_lng = float(driver_lng)
        except (TypeError, ValueError):
            continue

        last_seen = meta.get("last_seen")
        try:
            last_seen = int(float(last_seen)) if last_seen is not None else None
        except (TypeError, ValueError):
            last_seen = None
        if last_seen is None or (int(time.time()) - last_seen) > DRIVER_META_TTL_SECONDS:
            continue

        await publish_event("driver", driver_id, "ride_request", payload)
        count += 1

    return count


async def publish_ride_request_to_driver(
    driver_id: str,
    ride_id: str,
    pickup: str,
    destination: str,
    vehicle_type: str,
    fare_estimate: Optional[float],
    rider_id: Optional[str],
) -> None:
    payload = RideRequestEvent(
        rideId=ride_id,
        pickup=pickup,
        destination=destination,
        vehicleType=vehicle_type,
        fareEstimate=fare_estimate,
        riderId=rider_id,
    )
    await publish_event("driver", driver_id, "ride_request", payload)


async def publish_ride_request(
    ride_id: str,
    pickup: str,
    destination: str,
    vehicle_type: str,
    fare_estimate: Optional[float],
    rider_id: Optional[str],
    pickup_location: Optional[tuple[float, float]] = None,
) -> int:
    payload = RideRequestEvent(
        rideId=ride_id,
        pickup=pickup,
        destination=destination,
        vehicleType=vehicle_type,
        fareEstimate=fare_estimate,
        riderId=rider_id,
    )
    return await publish_ride_request_to_drivers(payload, pickup_location=pickup_location)


async def cleanup_stale_driver_locations() -> int:
    """
    Remove drivers from the GEO index whose presence metadata is stale.
    Returns the number of entries removed.
    """
    now = int(time.time())
    removed = 0
    driver_ids = await async_redis.zrange(DRIVER_GEO_INDEX, 0, -1)
    for driver_id in driver_ids:
        meta = await get_driver_presence(driver_id)
        if not meta:
            await async_redis.zrem(DRIVER_GEO_INDEX, driver_id)
            removed += 1
            continue
        last_seen = meta.get("last_seen")
        try:
            last_seen = int(float(last_seen)) if last_seen is not None else None
        except (TypeError, ValueError):
            last_seen = None
        if last_seen is None or (now - last_seen) > DRIVER_META_TTL_SECONDS:
            await async_redis.zrem(DRIVER_GEO_INDEX, driver_id)
            await delete_driver_presence(driver_id)
            removed += 1
    return removed
