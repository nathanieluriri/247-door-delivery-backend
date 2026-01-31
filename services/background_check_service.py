from __future__ import annotations

from schemas.background_check import (
    BackgroundCheckCreate,
    BackgroundCheckOut,
    BackgroundCheckUpdate,
    BackgroundStatus,
)
from repositories.background_check_repo import (
    create_background_check,
    get_background_check,
    update_background_check,
)


async def ensure_background_record(driver_id: str) -> BackgroundCheckOut:
    existing = await get_background_check(driver_id)
    if existing:
        return existing
    return await create_background_check(BackgroundCheckCreate(driverId=driver_id))


async def record_background_result(driver_id: str, status: BackgroundStatus, notes: str | None = None, reference: str | None = None):
    return await update_background_check(
        driver_id, BackgroundCheckUpdate(status=status, notes=notes, referenceId=reference)
    )


async def fetch_background_check(driver_id: str) -> BackgroundCheckOut | None:
    return await get_background_check(driver_id)
