import asyncio
import logging
import os
import time
import uuid
from typing import Iterable, Optional

from fastapi import Request
from pydantic import BaseModel

from core.redis_cache import async_redis
from core.metrics import sse_backlog
from core.routing_config import DeliveryRouteResponse
from services.notification_service import send_notification
from services.notification_targets import get_push_tokens, get_user_email
from schemas.sse import (
    SSEEvent,
    RideStatusUpdate,
    ChatMessageEvent,
    RideRequestEvent,
    DriverRouteUpdate,
    SSEEventType,
)


RETRY_AFTER_SECONDS = int(os.getenv("SSE_RETRY_AFTER_SECONDS", "5"))
EVENT_TTL_SECONDS = int(os.getenv("SSE_EVENT_TTL_SECONDS", "86400"))
POLL_INTERVAL_SECONDS = float(os.getenv("SSE_POLL_INTERVAL_SECONDS", "1"))
DRIVER_DISCOVERY_RADIUS_KM = float(os.getenv("DRIVER_DISCOVERY_RADIUS_KM", "5"))
DRIVER_META_TTL_SECONDS = int(os.getenv("DRIVER_META_TTL_SECONDS", "120"))
DRIVER_GEO_INDEX = os.getenv("DRIVER_GEO_INDEX", "drivers:geo_index")
DRIVER_DISPATCH_LOG_FILE = os.getenv("DRIVER_DISPATCH_LOG_FILE", "log_file.md")


def _append_dispatch_log(line: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    try:
        with open(DRIVER_DISPATCH_LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp} UTC] {line}\n")
    except Exception:
        pass


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


async def _notify_user(
    user_type: str,
    user_id: str,
    title: str,
    body: str,
    allow_email: bool = True,
) -> None:
    try:
        player_ids = await get_push_tokens(user_type, user_id)
        email = await get_user_email(user_type, user_id)
        payload: dict = {"title": title, "body": body}
        if player_ids:
            payload["player_ids"] = player_ids
        if email:
            payload["email"] = email
        if not payload.get("player_ids") and not payload.get("email"):
            return
        await send_notification(payload, allow_email=allow_email)
    except Exception:
        pass


def _schedule_notification(*args, **kwargs) -> None:
    try:
        asyncio.create_task(_notify_user(*args, **kwargs))
    except Exception:
        pass


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
    _append_dispatch_log(
        f"update_driver_presence:start id={driver_id} lat={latitude} lng={longitude} "
        f"vehicle_type={vehicle_type} profile_complete={profile_complete} account_status={account_status}"
    )
    try:
        geo_args = (float(longitude), float(latitude), str(driver_id))
        await async_redis.geoadd(DRIVER_GEO_INDEX, geo_args,nx=True)
        # await async_redis.geoadd(DRIVER_GEO_INDEX,float(longitude),float(latitude),str(driver_id),) # type: ignore

        
        _append_dispatch_log(f"update_driver_presence:geoadd_ok id={driver_id}")
    except Exception as exc:
        _append_dispatch_log(f"update_driver_presence:geoadd_error id={driver_id} error={exc}")
        raise

    try:
        await set_driver_presence(
            driver_id,
            {
                "vehicle_type": _normalize_vehicle_type(vehicle_type) or "unknown",
                "latitude": latitude,
                "longitude": longitude,
                "last_seen": now,
                "profile_complete": "1" if profile_complete else "0",
                "account_status": (account_status or "active").lower(),
            },
        )
        _append_dispatch_log(f"update_driver_presence:presence_ok id={driver_id} last_seen={now}")
    except Exception as exc:
        _append_dispatch_log(f"update_driver_presence:presence_error id={driver_id} error={exc}")
        raise


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
    event_types: Optional[Iterable[str | SSEEventType]] = None,
    ride_id: Optional[str] = None,
):
    logger = logging.getLogger(__name__)
    session_id = None
    active_key = None
    pending_key = _pending_key(user_type, user_id)
    allowed_types = (
        {
            event_type.value if isinstance(event_type, SSEEventType) else event_type
            for event_type in event_types
        }
        if event_types
        else None
    )

    try:
        # Open the SSE stream before any backend calls to ensure the client gets a readable stream.
        yield ": connected\n\n"
        await register_subscriber(user_type, user_id)
        if user_type == "driver":
            session_id = uuid.uuid4().hex
            active_key = _active_session_key(user_type, user_id)
            await async_redis.set(active_key, session_id, ex=EVENT_TTL_SECONDS)

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
            sse_backlog.observe(len(pending_ids))
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
    except Exception as exc:
        logger.exception("SSE stream failed for %s:%s", user_type, user_id)
        error_event = SSEEvent(
            id=uuid.uuid4().hex,
            event="sse_error",
            data={"message": "SSE stream failed", "detail": str(exc)},
            created_at=int(time.time()),
        )
        yield _format_sse(error_event)
    finally:
        try:
            if session_id and active_key:
                current_session = await async_redis.get(active_key)
                if current_session == session_id:
                    await async_redis.delete(active_key)
                    await delete_driver_presence(user_id)
                    await unregister_subscriber(user_type, user_id)
            else:
                await unregister_subscriber(user_type, user_id)
        except Exception:
            pass


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
        _schedule_notification(
            "rider",
            rider_id,
            "Ride status update",
            f"Ride {ride_id} status changed to {status}",
            allow_email=True,
        )
    if driver_id:
        await publish_event("driver", driver_id, "ride_status_update", payload)
        _schedule_notification(
            "driver",
            driver_id,
            "Ride status update",
            f"Ride {ride_id} status changed to {status}",
            allow_email=True,
        )


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

    # Push notify the other party only
    sender_value = (
        sender_type.value if hasattr(sender_type, "value") else str(sender_type)
    )
    sender_value = sender_value.lower()
    if sender_value == "driver" and rider_id:
        _schedule_notification(
            "rider",
            rider_id,
            "New message from driver",
            message,
            allow_email=True,
        )
    if sender_value == "rider" and driver_id:
        _schedule_notification(
            "driver",
            driver_id,
            "New message from rider",
            message,
            allow_email=True,
        )


async def publish_driver_route_update(
    ride_id: str,
    status,
    rider_id: Optional[str],
    driver_id: Optional[str],
    route: Optional[DeliveryRouteResponse] = None,
    error: Optional[str] = None,
) -> None:
    payload = DriverRouteUpdate(
        rideId=ride_id,
        status=status,
        route=route,
        generatedAt=int(time.time()),
        error=error,
    )
    if rider_id:
        await publish_event("rider", rider_id, "driver_route_update", payload)
    if driver_id:
        await publish_event("driver", driver_id, "driver_route_update", payload)


async def publish_ride_request_to_drivers(
    payload: RideRequestEvent,
    pickup_location: Optional[tuple[float, float]] = None,
) -> int:
    pickup_lat = None
    pickup_lng = None
    if pickup_location:
        pickup_lat, pickup_lng = pickup_location

    if pickup_lat is None or pickup_lng is None:
        _append_dispatch_log("publish_ride_request_to_drivers: missing pickup_location, abort")
        return 0

    requested_vehicle = _normalize_vehicle_type(payload.vehicle_type)
    _append_dispatch_log(
        f"publish_ride_request_to_drivers: ride_id={payload.ride_id} requested_vehicle={requested_vehicle} "
        f"pickup_lat={pickup_lat} pickup_lng={pickup_lng}"
    )
    count = 0
    driver_ids = await async_redis.georadius(
        name=DRIVER_GEO_INDEX,
        longitude=pickup_lng,
        latitude=pickup_lat,
        radius=DRIVER_DISCOVERY_RADIUS_KM,
        unit="km",
    )
    _append_dispatch_log(
        f"geo_candidates: count={len(driver_ids)} radius_km={DRIVER_DISCOVERY_RADIUS_KM}"
    )
    for driver_id in driver_ids:
        _append_dispatch_log(f"driver_candidate: id={driver_id}")
        meta = await get_driver_presence(driver_id)
        if not meta:
            _append_dispatch_log(f"driver_skip: id={driver_id} reason=missing_presence")
            continue
        if meta.get("account_status") not in {"active"}:
            _append_dispatch_log(
                f"driver_skip: id={driver_id} reason=account_status "
                f"value={meta.get('account_status')}"
            )
            continue

        if meta.get("profile_complete") not in {"1", "true", "True", "TRUE"}:
            _append_dispatch_log(
                f"driver_skip: id={driver_id} reason=profile_complete "
                f"value={meta.get('profile_complete')}"
            )
            continue

        driver_vehicle = _normalize_vehicle_type(meta.get("vehicle_type"))
        _append_dispatch_log(
            f"driver_meta_vehicle: id={driver_id} vehicle_type={driver_vehicle}"
        )
        if requested_vehicle and driver_vehicle and driver_vehicle != requested_vehicle:
            _append_dispatch_log(
                f"driver_skip: id={driver_id} reason=vehicle_mismatch "
                f"driver={driver_vehicle} requested={requested_vehicle}"
            )
            continue

        if requested_vehicle and not driver_vehicle:
            _append_dispatch_log(
                f"driver_skip: id={driver_id} reason=vehicle_missing requested={requested_vehicle}"
            )
            continue

        driver_lat = meta.get("latitude")
        driver_lng = meta.get("longitude")
        if pickup_lat is None or pickup_lng is None or driver_lat is None or driver_lng is None:
            _append_dispatch_log(f"driver_skip: id={driver_id} reason=missing_coords")
            continue

        try:
            driver_lat = float(driver_lat)
            driver_lng = float(driver_lng)
        except (TypeError, ValueError):
            _append_dispatch_log(f"driver_skip: id={driver_id} reason=invalid_coords")
            continue

        last_seen = meta.get("last_seen")
        try:
            last_seen = int(float(last_seen)) if last_seen is not None else None
        except (TypeError, ValueError):
            last_seen = None
        if last_seen is None or (int(time.time()) - last_seen) > DRIVER_META_TTL_SECONDS:
            _append_dispatch_log(
                f"driver_skip: id={driver_id} reason=stale last_seen={last_seen}"
            )
            continue

        await publish_event("driver", driver_id, "ride_request", payload)
        _schedule_notification(
            "driver",
            str(driver_id),
            "New ride request",
            f"{payload.pickup} → {payload.destination}",
            allow_email=False,
        )
        _append_dispatch_log(f"driver_publish: id={driver_id} ride_id={payload.ride_id}")
        count += 1

    _append_dispatch_log(
        f"publish_complete: ride_id={payload.ride_id} published_to={count}"
    )
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
    _schedule_notification(
        "driver",
        driver_id,
        "New ride request",
        f"{pickup} → {destination}",
        allow_email=False,
    )


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
