from fastapi import APIRouter, Depends, HTTPException
from schemas.response_schema import APIResponse
from security.auth import verify_admin_token
from services.quarantine_service import QUARANTINE_LOG_KEY
from core.redis_cache import async_redis

router = APIRouter(prefix="/quarantine", tags=["Admin"])


@router.get("/", response_model=APIResponse[list], dependencies=[Depends(verify_admin_token)])
async def list_quarantine_events(limit: int = 100):
    records = await async_redis.lrange(QUARANTINE_LOG_KEY, 0, limit - 1)
    return APIResponse(status_code=200, data=[r for r in records], detail="Quarantine events")
