import asyncio
import json
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


def _pending_key(user_type: str, user_id: str) -> str:
    return f"sse:pending:{user_type}:{user_id}"


def _event_key(event_id: str) -> str:
    return f"sse:event:{event_id}"


def _subscribers_key(user_type: str) -> str:
    return f"sse:subscribers:{user_type}"


def _format_sse(event: SSEEvent) -> str:
    payload = event.model_dump_json(by_alias=True)
    return f"id: {event.id}\nevent: {event.event}\ndata: {payload}\n\n"


async def register_subscriber(user_type: str, user_id: str) -> None:
    await async_redis.sadd(_subscribers_key(user_type), user_id)


async def unregister_subscriber(user_type: str, user_id: str) -> None:
    await async_redis.srem(_subscribers_key(user_type), user_id)


async def get_subscribers(user_type: str) -> Iterable[str]:
    return await async_redis.smembers(_subscribers_key(user_type))


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
    pending_key = _pending_key(user_type, user_id)
    allowed_types = set(event_types) if event_types else None

    try:
        while True:
            if await request.is_disconnected():
                break

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


async def publish_ride_request_to_drivers(payload: RideRequestEvent) -> int:
    driver_ids = await get_subscribers("driver")
    count = 0
    for driver_id in driver_ids:
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
) -> int:
    payload = RideRequestEvent(
        rideId=ride_id,
        pickup=pickup,
        destination=destination,
        vehicleType=vehicle_type,
        fareEstimate=fare_estimate,
        riderId=rider_id,
    )
    return await publish_ride_request_to_drivers(payload)
