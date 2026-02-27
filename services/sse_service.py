import asyncio
import json
import logging
import os
import time
import uuid
from typing import Iterable, Optional, Sequence

from fastapi import Request
from pydantic import BaseModel

from core.redis_cache import async_redis
from core.metrics import (
    sse_ack_latency_seconds,
    sse_backlog,
    sse_dead_lettered_total,
    sse_events_acked_total,
    sse_events_delivered_total,
    sse_events_published_total,
    sse_queue_overflow_drops_total,
)
from core.routing_config import DeliveryRouteResponse
from services.driver_snapshot_service import build_driver_sse_snapshot
from services.notification_service import send_notification
from services.notification_targets import get_push_tokens, get_user_email
from schemas.imports import RideStatus
from schemas.sse import (
    SSEEvent,
    DriverSnapshot,
    RideStatusUpdate,
    ProfileActionRequiredEvent,
    ChatMessageEvent,
    RideRequestEvent,
    DriverRouteUpdate,
    SSEEventType,
)
from schemas.ride import RideRatingStatus


RETRY_AFTER_SECONDS = int(os.getenv("SSE_RETRY_AFTER_SECONDS", "5"))
EVENT_TTL_SECONDS = int(os.getenv("SSE_EVENT_TTL_SECONDS", "86400"))
POLL_INTERVAL_SECONDS = float(os.getenv("SSE_POLL_INTERVAL_SECONDS", "1"))
PENDING_SCAN_LIMIT = int(os.getenv("SSE_PENDING_SCAN_LIMIT", "100"))
MAX_DELIVERIES_PER_TICK = int(os.getenv("SSE_MAX_DELIVERIES_PER_TICK", "20"))
MAX_PENDING_EVENTS = int(os.getenv("SSE_MAX_PENDING_EVENTS", "500"))
MAX_DELIVERY_ATTEMPTS = int(os.getenv("SSE_MAX_DELIVERY_ATTEMPTS", "25"))
MAX_EVENT_AGE_SECONDS = int(os.getenv("SSE_MAX_EVENT_AGE_SECONDS", str(EVENT_TTL_SECONDS)))
DEAD_LETTER_TTL_SECONDS = int(os.getenv("SSE_DEAD_LETTER_TTL_SECONDS", "604800"))
DEAD_LETTER_MAX_ITEMS = int(os.getenv("SSE_DEAD_LETTER_MAX_ITEMS", "1000"))
DRIVER_DISCOVERY_RADIUS_KM = float(os.getenv("DRIVER_DISCOVERY_RADIUS_KM", "5"))
DRIVER_META_TTL_SECONDS = int(os.getenv("DRIVER_META_TTL_SECONDS", "120"))
DRIVER_GEO_INDEX = os.getenv("DRIVER_GEO_INDEX", "drivers:geo_index")
DRIVER_DISPATCH_LOG_FILE = os.getenv("DRIVER_DISPATCH_LOG_FILE", "log_file.md")
PROFILE_ACTION_PROMPT_COOLDOWN_SECONDS = int(os.getenv("PROFILE_ACTION_PROMPT_COOLDOWN_SECONDS", "86400"))


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


def _dead_letter_key(user_type: str, user_id: str) -> str:
    return f"sse:dead_letter:{user_type}:{user_id}"


def _subscribers_key(user_type: str) -> str:
    return f"sse:subscribers:{user_type}"


def _driver_presence_key(driver_id: str) -> str:
    return f"sse:driver_presence:{driver_id}"


def _active_session_key(user_type: str, user_id: str) -> str:
    return f"sse:session:{user_type}:{user_id}"


def _profile_action_prompt_key(user_type: str, user_id: str, action_type: str) -> str:
    return f"sse:profile_action_prompt:{user_type}:{user_id}:{action_type}"


def _format_sse(event: SSEEvent) -> str:
    payload = event.model_dump_json(by_alias=True)
    return f"id: {event.id}\nevent: {event.event}\ndata: {payload}\n\n"


def _resolve_replay_cursor_id(request: Request, last_event_id: Optional[str]) -> Optional[str]:
    if last_event_id:
        value = last_event_id.strip()
        if value:
            return value
    header_value = request.headers.get("last-event-id")
    if not header_value:
        return None
    value = header_value.strip()
    return value or None


def _pending_after_cursor(pending_ids: Sequence[str], cursor_id: str) -> list[str]:
    try:
        index = list(pending_ids).index(cursor_id)
    except ValueError:
        return list(pending_ids)
    return list(pending_ids[index + 1 :])


async def _move_to_dead_letter(
    *,
    user_type: str,
    user_id: str,
    event_id: str,
    reason: str,
    record: Optional[dict] = None,
    remove_from_pending: bool = True,
) -> None:
    event_key = _event_key(event_id)
    pending_key = _pending_key(user_type, user_id)
    dead_key = _dead_letter_key(user_type, user_id)
    event_record = record or await async_redis.hgetall(event_key)

    payload = {
        "event_id": event_id,
        "reason": reason,
        "moved_at": int(time.time()),
        "event_type": event_record.get("event_type"),
        "created_at": event_record.get("created_at"),
        "last_sent_at": event_record.get("last_sent_at"),
        "delivery_attempts": event_record.get("delivery_attempts"),
    }
    event_payload = event_record.get("payload")
    if event_payload:
        payload["payload"] = event_payload

    pipe = async_redis.pipeline()
    pipe.rpush(dead_key, json.dumps(payload))
    pipe.expire(dead_key, DEAD_LETTER_TTL_SECONDS)
    pipe.ltrim(dead_key, -DEAD_LETTER_MAX_ITEMS, -1)
    if remove_from_pending:
        pipe.lrem(pending_key, 0, event_id)
    pipe.delete(event_key)
    await pipe.execute()
    sse_dead_lettered_total.labels(reason=reason, user_type=user_type).inc()


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


async def list_eligible_driver_ids_for_request(
    pickup_location: tuple[float, float],
    vehicle_type: Optional[str],
) -> list[str]:
    pickup_lat, pickup_lng = pickup_location
    requested_vehicle = _normalize_vehicle_type(vehicle_type)
    now = int(time.time())
    driver_ids = await async_redis.georadius(
        name=DRIVER_GEO_INDEX,
        longitude=pickup_lng,
        latitude=pickup_lat,
        radius=DRIVER_DISCOVERY_RADIUS_KM,
        unit="km",
    )
    eligible_driver_ids: list[str] = []
    for raw_driver_id in driver_ids:
        driver_id = str(raw_driver_id)
        meta = await get_driver_presence(driver_id)
        if not meta:
            continue
        if str(meta.get("account_status") or "").strip().lower() != "active":
            continue
        if str(meta.get("profile_complete") or "").strip().lower() not in {"1", "true"}:
            continue

        driver_vehicle = _normalize_vehicle_type(meta.get("vehicle_type"))
        if requested_vehicle and driver_vehicle != requested_vehicle:
            continue

        driver_lat = meta.get("latitude")
        driver_lng = meta.get("longitude")
        if driver_lat is None or driver_lng is None:
            continue
        try:
            float(driver_lat)
            float(driver_lng)
        except (TypeError, ValueError):
            continue

        last_seen = meta.get("last_seen")
        try:
            last_seen = int(float(last_seen)) if last_seen is not None else None
        except (TypeError, ValueError):
            last_seen = None
        if last_seen is None or (now - last_seen) > DRIVER_META_TTL_SECONDS:
            continue

        eligible_driver_ids.append(driver_id)
    return eligible_driver_ids


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
        await async_redis.geoadd(DRIVER_GEO_INDEX, geo_args)
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
            "delivery_attempts": "0",
        },
    )
    pipe.expire(event_key, EVENT_TTL_SECONDS)
    pipe.rpush(pending_key, event_id)
    await pipe.execute()
    sse_events_published_total.labels(event_type=event_type, user_type=user_type).inc()

    pending_size = await async_redis.llen(pending_key)
    if pending_size > MAX_PENDING_EVENTS:
        overflow = pending_size - MAX_PENDING_EVENTS
        for _ in range(max(overflow, 0)):
            dropped_event_id = await async_redis.lpop(pending_key)
            if not dropped_event_id:
                break
            await _move_to_dead_letter(
                user_type=user_type,
                user_id=user_id,
                event_id=dropped_event_id,
                reason="queue_overflow",
                remove_from_pending=False,
            )
            sse_queue_overflow_drops_total.labels(user_type=user_type).inc()
    return event


async def ack_event(user_type: str, user_id: str, event_id: str) -> bool:
    event_key = _event_key(event_id)
    record = await async_redis.hgetall(event_key)
    if not record:
        return False
    if record.get("user_type") != user_type or record.get("user_id") != user_id:
        return False
    event_type = str(record.get("event_type") or "unknown")
    created_at_raw = record.get("created_at")
    created_at: Optional[int] = None
    if created_at_raw is not None:
        try:
            created_at = int(float(created_at_raw))
        except (TypeError, ValueError):
            created_at = None

    pipe = async_redis.pipeline()
    pipe.lrem(_pending_key(user_type, user_id), 0, event_id)
    pipe.delete(event_key)
    await pipe.execute()
    sse_events_acked_total.labels(event_type=event_type, user_type=user_type).inc()
    if created_at is not None:
        latency = max(int(time.time()) - created_at, 0)
        sse_ack_latency_seconds.labels(event_type=event_type, user_type=user_type).observe(
            latency
        )
    return True


async def stream_events(
    request: Request,
    user_type: str,
    user_id: str,
    event_types: Optional[Iterable[str | SSEEventType]] = None,
    ride_id: Optional[str] = None,
    last_event_id: Optional[str] = None,
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
    replay_cursor_id = _resolve_replay_cursor_id(request, last_event_id)
    replay_cursor_applied = False
    replay_pending_ids: list[str] = []
    replay_index = 0

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
            pending_length = await async_redis.llen(pending_key)
            replay_pass = False
            if replay_cursor_id and not replay_cursor_applied:
                replay_source = await async_redis.lrange(pending_key, 0, -1)
                replay_pending_ids = _pending_after_cursor(replay_source, replay_cursor_id)
                replay_cursor_applied = True
            if replay_index < len(replay_pending_ids):
                replay_pass = True
                scan_size = max(PENDING_SCAN_LIMIT, 1)
                pending_ids = replay_pending_ids[replay_index : replay_index + scan_size]
            else:
                pending_ids = await async_redis.lrange(
                    pending_key, 0, max(PENDING_SCAN_LIMIT, 1) - 1
                )
            sse_backlog.observe(pending_length)
            sent_any = False
            sent_count = 0

            for event_id in pending_ids:
                if replay_pass:
                    replay_index += 1
                if sent_count >= MAX_DELIVERIES_PER_TICK:
                    break
                event_key = _event_key(event_id)
                record = await async_redis.hgetall(event_key)
                if not record:
                    await async_redis.lrem(pending_key, 0, event_id)
                    continue

                if record.get("user_type") != user_type or record.get("user_id") != user_id:
                    continue

                created_at = int(float(record.get("created_at") or 0))
                if created_at and (now - created_at) > MAX_EVENT_AGE_SECONDS:
                    await _move_to_dead_letter(
                        user_type=user_type,
                        user_id=user_id,
                        event_id=event_id,
                        reason="max_event_age_exceeded",
                        record=record,
                    )
                    continue

                delivery_attempts = int(float(record.get("delivery_attempts") or 0))
                if delivery_attempts >= MAX_DELIVERY_ATTEMPTS:
                    await _move_to_dead_letter(
                        user_type=user_type,
                        user_id=user_id,
                        event_id=event_id,
                        reason="max_delivery_attempts_exceeded",
                        record=record,
                    )
                    continue

                last_sent_at = int(float(record.get("last_sent_at") or 0))
                if (not replay_pass) and (now - last_sent_at < RETRY_AFTER_SECONDS):
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

                await async_redis.hset(
                    event_key,
                    mapping={
                        "last_sent_at": str(now),
                        "delivery_attempts": str(delivery_attempts + 1),
                    },
                )
                sent_any = True
                sent_count += 1
                sse_events_delivered_total.labels(
                    event_type=event.event, user_type=user_type
                ).inc()
                yield _format_sse(event)

            if not sent_any:
                yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    except Exception as exc:
        logger.exception("SSE stream failed for %s:%s", user_type, user_id)
        error_event = SSEEvent(
            id=uuid.uuid4().hex,
            event="sse_error",
            data={
                "message": "SSE stream failed",
                "code": "SSE_STREAM_ERROR",
            },
            created_at=int(time.time()),
        )
        yield _format_sse(error_event)
    finally:
        try:
            if session_id and active_key:
                current_session = await async_redis.get(active_key)
                if current_session == session_id:
                    await async_redis.delete(active_key)
                    await unregister_subscriber(user_type, user_id)
            else:
                await unregister_subscriber(user_type, user_id)
        except Exception:
            pass


async def publish_ride_status_update(
    ride_id: str,
    status: RideStatus,
    rider_id: Optional[str],
    driver_id: Optional[str],
    message: Optional[str] = None,
    eta_minutes: Optional[int] = None,
    action_required: Optional[bool] = None,
    action_type: Optional[str] = None,
    decision_options: Optional[list[str]] = None,
    action_deadline_ms: Optional[int] = None,
    reason_code: Optional[str] = None,
    rating_status: Optional[RideRatingStatus] = None,
) -> None:
    status_value = status.value if hasattr(status, "value") else str(status)
    base_payload = RideStatusUpdate(
        rideId=ride_id,
        status=status,
        message=message,
        etaMinutes=eta_minutes,
        actionRequired=action_required,
        actionType=action_type,
        decisionOptions=decision_options,
        actionDeadlineMs=action_deadline_ms,
        reasonCode=reason_code,
        ratingStatus=rating_status,
    )
    if rider_id:
        rider_payload = base_payload
        if driver_id:
            try:
                snapshot_data = await build_driver_sse_snapshot(driver_id)
                if snapshot_data:
                    rider_payload = base_payload.model_copy(
                        update={
                            "driver_snapshot": DriverSnapshot(**snapshot_data),
                        }
                    )
            except Exception:
                rider_payload = base_payload
        await publish_event("rider", rider_id, "ride_status_update", rider_payload)
        _schedule_notification(
            "rider",
            rider_id,
            "Ride status update",
            f"Ride {ride_id} status changed to {status_value}",
            allow_email=True,
        )
    if driver_id:
        await publish_event("driver", driver_id, "ride_status_update", base_payload)
        _schedule_notification(
            "driver",
            driver_id,
            "Ride status update",
            f"Ride {ride_id} status changed to {status_value}",
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
    status: RideStatus,
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


async def publish_profile_action_required(
    *,
    user_type: str,
    user_id: str,
    action_type: str,
    message: str,
    field: str,
    required: bool = False,
    severity: str = "info",
    cta_label: Optional[str] = None,
    cta_path: Optional[str] = None,
    cooldown_seconds: Optional[int] = PROFILE_ACTION_PROMPT_COOLDOWN_SECONDS,
) -> Optional[SSEEvent]:
    if cooldown_seconds is not None and cooldown_seconds > 0:
        dedupe_key = _profile_action_prompt_key(user_type, user_id, action_type)
        if await async_redis.exists(dedupe_key):
            return None
        await async_redis.set(dedupe_key, "1", ex=cooldown_seconds)

    payload = ProfileActionRequiredEvent(
        actionType=action_type,
        message=message,
        field=field,
        required=required,
        severity=severity,
        ctaLabel=cta_label,
        ctaPath=cta_path,
    )
    return await publish_event(user_type, user_id, SSEEventType.profile_action_required.value, payload)


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
    eligible_driver_ids = await list_eligible_driver_ids_for_request(
        pickup_location=(pickup_lat, pickup_lng),
        vehicle_type=payload.vehicle_type,
    )
    _append_dispatch_log(
        f"eligible_candidates: count={len(eligible_driver_ids)} radius_km={DRIVER_DISCOVERY_RADIUS_KM}"
    )
    count = 0
    for driver_id in eligible_driver_ids:
        await publish_event("driver", str(driver_id), "ride_request", payload)
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
