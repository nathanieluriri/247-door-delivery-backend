from services.quarantine_service import log_quarantine_event, QUARANTINE_LOG_KEY
from core.redis_cache import async_redis
import asyncio
import pytest


@pytest.mark.asyncio
async def test_log_quarantine_event():
    await async_redis.delete(QUARANTINE_LOG_KEY)
    await log_quarantine_event("driver1", "fileKey", "virus")
    items = await async_redis.lrange(QUARANTINE_LOG_KEY, 0, -1)
    assert len(items) == 1
