import os
from typing import List, Optional

from bson import ObjectId

from core.redis_cache import async_redis
from repositories.driver import get_driver
from repositories.rider_repo import get_rider

PUSH_TOKEN_TTL_SECONDS = int(os.getenv("PUSH_TOKEN_TTL_SECONDS", str(30 * 24 * 60 * 60)))


def _push_key(user_type: str, user_id: str) -> str:
    return f"push:player_ids:{user_type}:{user_id}"


async def register_push_token(user_type: str, user_id: str, player_id: str) -> List[str]:
    if not player_id:
        return []
    key = _push_key(user_type, user_id)
    pipe = async_redis.pipeline()
    pipe.sadd(key, player_id)
    pipe.expire(key, PUSH_TOKEN_TTL_SECONDS)
    await pipe.execute()
    tokens = await async_redis.smembers(key)
    return list(tokens or [])


async def get_push_tokens(user_type: str, user_id: str) -> List[str]:
    tokens = await async_redis.smembers(_push_key(user_type, user_id))
    return list(tokens or [])


async def has_push_tokens(user_type: str, user_id: str) -> bool:
    return await async_redis.scard(_push_key(user_type, user_id)) > 0


async def get_user_email(user_type: str, user_id: str) -> Optional[str]:
    if not ObjectId.is_valid(user_id):
        return None
    if user_type == "driver":
        user = await get_driver({"_id": ObjectId(user_id)})
    elif user_type == "rider":
        user = await get_rider({"_id": ObjectId(user_id)})
    else:
        return None
    return getattr(user, "email", None) if user else None
