"""Repository for admin activity logs."""

from __future__ import annotations

from typing import Any, Optional

from core.database import db


async def add_admin_activity(payload: dict[str, Any]) -> dict:
    """Insert an admin activity log and return the created document."""
    result = await db.admin_activity_logs.insert_one(payload)
    created = await db.admin_activity_logs.find_one({"_id": result.inserted_id})
    created["id"] = str(created.pop("_id"))
    return created


async def list_admin_activity_logs(
    *,
    admin_id: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    limit: int = 100,
    skip: int = 0,
) -> list[dict]:
    query: dict[str, Any] = {}
    if admin_id:
        query["adminId"] = admin_id
    if method:
        query["method"] = method
    if path:
        query["path"] = path
    if from_ts is not None or to_ts is not None:
        ts_query: dict[str, Any] = {}
        if from_ts is not None:
            ts_query["$gte"] = from_ts
        if to_ts is not None:
            ts_query["$lte"] = to_ts
        query["timestamp"] = ts_query

    cursor = db.admin_activity_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    results: list[dict] = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        results.append(doc)
    return results
