"""
Notification service with push + SMS fallback and dead-letter queue.

This is a lightweight adapter; integrate real providers by implementing
`send_push_impl` and `send_sms_impl`.
"""

from __future__ import annotations

import os
import json
import time
from typing import Optional

from core.redis_cache import async_redis
from services.push_notification import send_push
from services.email_notification import send_email

DLQ_KEY = os.getenv("NOTIFY_DLQ_KEY", "notifications:dlq")
RETRY_KEY = os.getenv("NOTIFY_RETRY_KEY", "notifications:retry")
MAX_RETRIES = int(os.getenv("NOTIFY_MAX_RETRIES", "3"))


async def _enqueue_dlq(payload: dict):
    await async_redis.lpush(DLQ_KEY, json.dumps(payload))


async def _send_push_impl(payload: dict) -> bool:
    player_ids = payload.get("player_ids") or payload.get("include_player_ids")
    heading = payload.get("title") or "Notification"
    content = payload.get("body") or payload.get("message") or ""
    return send_push(player_ids, heading, content)


async def _send_sms_impl(payload: dict) -> bool:
    # Placeholder: SMS not implemented
    return False


async def _send_email_impl(payload: dict) -> bool:
    to_email = payload.get("email")
    subject = payload.get("title") or "Notification"
    body = payload.get("body") or payload.get("message") or ""
    if not to_email:
        return False
    return send_email(to_email, subject, body)


async def send_notification(payload: dict, allow_sms: bool = True, allow_email: bool = True):
    attempt = int(payload.get("attempt", 0))
    payload["attempt"] = attempt + 1
    sent = await _send_push_impl(payload)
    if sent:
        return True
    if allow_sms:
        sent = await _send_sms_impl(payload)
        if sent:
            return True
    if allow_email:
        sent = await _send_email_impl(payload)
        if sent:
            return True
    if payload["attempt"] >= MAX_RETRIES:
        payload["failed_at"] = int(time.time())
        await _enqueue_dlq(payload)
    else:
        await async_redis.lpush(RETRY_KEY, json.dumps(payload))
    return False
