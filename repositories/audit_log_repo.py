"""Simple audit log repository for admin and system actions.

Stores lightweight records in the `audit_logs` collection. Each log entry captures
who performed an action, what resource was affected, and optional metadata for
traceability. This keeps the DB schema minimal while giving us a consistent
place to write verification decisions, document changes, bans, etc.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from bson import ObjectId
from fastapi import HTTPException

from core.database import db


async def add_audit_log(
    *,
    actor_id: str,
    actor_type: str,
    action: str,
    target_type: str,
    target_id: str,
    metadata: Optional[dict[str, Any]] = None,
) -> dict:
    """Insert an audit record and return the created document."""

    if not actor_id or not action or not target_id:
        raise HTTPException(status_code=400, detail="Missing audit log fields")

    document = {
        "actorId": actor_id,
        "actorType": actor_type,
        "action": action,
        "targetType": target_type,
        "targetId": target_id,
        "metadata": metadata or {},
        "createdAt": int(time.time()),
    }

    result = await db.audit_logs.insert_one(document)
    created = await db.audit_logs.find_one({"_id": result.inserted_id})
    created["id"] = str(created.pop("_id"))
    return created


async def list_audit_logs_for_target(target_id: str, target_type: str, limit: int = 50):
    cursor = (
        db.audit_logs.find({"targetId": target_id, "targetType": target_type})
        .sort("createdAt", -1)
        .limit(limit)
    )
    results = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        results.append(doc)
    return results

