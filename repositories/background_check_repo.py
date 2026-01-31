from __future__ import annotations

from typing import Optional
from bson import ObjectId
from fastapi import HTTPException

from core.database import db
from schemas.background_check import (
    BackgroundCheckCreate,
    BackgroundCheckOut,
    BackgroundCheckUpdate,
    BackgroundStatus,
)


async def create_background_check(entry: BackgroundCheckCreate) -> BackgroundCheckOut:
    payload = entry.model_dump()
    result = await db.background_checks.insert_one(payload)
    created = await db.background_checks.find_one({"_id": result.inserted_id})
    return BackgroundCheckOut.model_validate_db(created)


async def get_background_check(driver_id: str) -> Optional[BackgroundCheckOut]:
    doc = await db.background_checks.find_one({"driverId": driver_id})
    if not doc:
        return None
    return BackgroundCheckOut.model_validate_db(doc)


async def update_background_check(driver_id: str, update: BackgroundCheckUpdate) -> BackgroundCheckOut:
    doc = await db.background_checks.find_one_and_update(
        {"driverId": driver_id},
        {"$set": update.model_dump(exclude_none=True)},
        return_document=True,
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Background check not found")
    return BackgroundCheckOut.model_validate_db(doc)
