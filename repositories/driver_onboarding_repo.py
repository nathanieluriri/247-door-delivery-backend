from __future__ import annotations

import time
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument

from core.database import db

_indexes_ready = False


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return

    collection = db.driver_onboarding_profiles
    if hasattr(collection, "create_index"):
        await collection.create_index([("driver_id", 1), ("provider", 1)], unique=True)
        await collection.create_index([("provider", 1), ("account_id", 1)], sparse=True)
    _indexes_ready = True


def _serialize_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    serialized = dict(doc)
    raw_id = serialized.get("_id")
    if isinstance(raw_id, ObjectId):
        serialized["id"] = str(raw_id)
    return serialized


def _merge_dict(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
            continue
        merged[key] = value
    return merged


async def get_driver_onboarding_profile(
    driver_id: str,
    provider: str = "fake",
) -> dict[str, Any] | None:
    await _ensure_indexes()
    doc = await db.driver_onboarding_profiles.find_one(
        {"driver_id": driver_id, "provider": provider}
    )
    return _serialize_doc(doc)


async def get_driver_onboarding_profile_by_account_id(
    account_id: str,
    provider: str = "fake",
) -> dict[str, Any] | None:
    await _ensure_indexes()
    doc = await db.driver_onboarding_profiles.find_one(
        {"provider": provider, "account_id": account_id}
    )
    return _serialize_doc(doc)


async def upsert_driver_onboarding_draft(
    *,
    driver_id: str,
    provider: str = "fake",
    account_id: str | None = None,
    draft_updates: dict[str, Any] | None = None,
    return_url: str | None = None,
) -> dict[str, Any]:
    await _ensure_indexes()
    now = int(time.time())
    existing = await db.driver_onboarding_profiles.find_one(
        {"driver_id": driver_id, "provider": provider}
    )

    if existing is None:
        draft = draft_updates or {}
        status_value = "in_progress" if (draft or return_url or account_id) else "not_started"
        payload = {
            "driver_id": driver_id,
            "provider": provider,
            "account_id": account_id,
            "status": status_value,
            "draft": draft,
            "completion": None,
            "return_url": return_url,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        result = await db.driver_onboarding_profiles.insert_one(payload)
        created = await db.driver_onboarding_profiles.find_one({"_id": result.inserted_id})
        return _serialize_doc(created) or payload

    merged_draft = _merge_dict(existing.get("draft") or {}, draft_updates or {})
    current_status = str(existing.get("status") or "not_started")
    next_status = current_status
    if current_status == "not_started" and (merged_draft or return_url or account_id):
        next_status = "in_progress"

    updated = await db.driver_onboarding_profiles.find_one_and_update(
        {"driver_id": driver_id, "provider": provider},
        {
            "$set": {
                "account_id": account_id or existing.get("account_id"),
                "draft": merged_draft,
                "return_url": return_url if return_url is not None else existing.get("return_url"),
                "status": next_status,
                "updated_at": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_doc(updated) or {
        **existing,
        "draft": merged_draft,
        "return_url": return_url if return_url is not None else existing.get("return_url"),
        "status": next_status,
        "updated_at": now,
    }


async def complete_driver_onboarding(
    *,
    driver_id: str,
    provider: str = "fake",
    account_id: str,
    completion: dict[str, Any],
    draft_updates: dict[str, Any] | None = None,
    return_url: str | None = None,
) -> dict[str, Any]:
    await _ensure_indexes()
    now = int(time.time())
    existing = await db.driver_onboarding_profiles.find_one(
        {"driver_id": driver_id, "provider": provider}
    )
    merged_draft = _merge_dict((existing or {}).get("draft") or {}, draft_updates or {})
    created_at = int((existing or {}).get("created_at") or now)

    updated = await db.driver_onboarding_profiles.find_one_and_update(
        {"driver_id": driver_id, "provider": provider},
        {
            "$set": {
                "account_id": account_id,
                "status": "completed",
                "completion": completion,
                "draft": merged_draft,
                "return_url": return_url if return_url is not None else (existing or {}).get("return_url"),
                "updated_at": now,
                "completed_at": now,
            },
            "$setOnInsert": {
                "driver_id": driver_id,
                "provider": provider,
                "created_at": created_at,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_doc(updated) or {
        "driver_id": driver_id,
        "provider": provider,
        "account_id": account_id,
        "status": "completed",
        "completion": completion,
        "draft": merged_draft,
        "return_url": return_url,
        "created_at": created_at,
        "updated_at": now,
        "completed_at": now,
    }
