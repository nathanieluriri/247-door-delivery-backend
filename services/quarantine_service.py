from __future__ import annotations

from repositories.audit_log_repo import add_audit_log
from core.redis_cache import async_redis
import json

QUARANTINE_LOG_KEY = "quarantine:events"


async def log_quarantine_event(driver_id: str, file_key: str, reason: str):
    payload = {"driverId": driver_id, "fileKey": file_key, "reason": reason}
    await async_redis.lpush(QUARANTINE_LOG_KEY, json.dumps(payload))
    await add_audit_log(
        actor_id="system",
        actor_type="system",
        action="quarantine_file",
        target_type="driver",
        target_id=driver_id,
        metadata=payload,
    )
