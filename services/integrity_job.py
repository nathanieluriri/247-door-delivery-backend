import asyncio
from core.redis_cache import async_redis
from core.storage import verify_integrity
from services.driver_document_service import get_driver_documents
from core.metrics import integrity_failures


async def reverify_hashes_for_driver(driver_id: str):
    docs = await get_driver_documents(driver_id)
    for d in docs:
        ok = verify_integrity(d.fileKey, d.sha256)
        if not ok:
            integrity_failures.inc()
    return True


async def reverify_all_drivers(driver_ids: list[str]):
    for driver_id in driver_ids:
        await reverify_hashes_for_driver(driver_id)
