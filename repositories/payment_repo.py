from __future__ import annotations

import time
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument

from core.database import db

_indexes_ready = False


async def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return

    await db.payment_transactions.create_index([("reference", 1)], unique=True)
    await db.payment_transactions.create_index(
        [("ride_id", 1)],
        unique=True,
        sparse=True,
    )
    await db.payment_transactions.create_index([("owner_id", 1)])
    await db.payment_webhook_events.create_index(
        [("provider", 1), ("event_id", 1)],
        unique=True,
    )

    _indexes_ready = True


def _serialize_payment_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    serialized = dict(doc)
    raw_id = serialized.get("_id")
    if isinstance(raw_id, ObjectId):
        serialized["id"] = str(raw_id)
    return serialized


async def create_payment_transaction(document: dict[str, Any]) -> dict[str, Any]:
    await _ensure_indexes()
    now = int(time.time())

    payload = {
        **document,
        "date_created": document.get("date_created", now),
        "last_updated": document.get("last_updated", now),
    }

    result = await db.payment_transactions.insert_one(payload)
    created = await db.payment_transactions.find_one({"_id": result.inserted_id})
    return _serialize_payment_doc(created) or payload


async def get_payment_transaction_by_reference(reference: str) -> dict[str, Any] | None:
    await _ensure_indexes()
    doc = await db.payment_transactions.find_one({"reference": reference})
    return _serialize_payment_doc(doc)


async def get_payment_transaction_by_ride_id(ride_id: str) -> dict[str, Any] | None:
    await _ensure_indexes()
    doc = await db.payment_transactions.find_one({"ride_id": ride_id})
    return _serialize_payment_doc(doc)


async def get_payment_transaction_by_provider_payment_id(provider_payment_id: str) -> dict[str, Any] | None:
    await _ensure_indexes()
    doc = await db.payment_transactions.find_one({"provider_payment_id": provider_payment_id})
    return _serialize_payment_doc(doc)


async def update_payment_transaction_status(
    reference: str,
    status_value: str,
    response_payload: dict[str, Any],
) -> dict[str, Any] | None:
    await _ensure_indexes()
    now = int(time.time())
    result = await db.payment_transactions.find_one_and_update(
        {"reference": reference},
        {
            "$set": {
                "status": status_value,
                "response_payload": response_payload,
                "last_updated": now,
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_payment_doc(result)


async def upsert_payment_transaction_by_reference(
    reference: str,
    document: dict[str, Any],
) -> dict[str, Any]:
    await _ensure_indexes()
    now = int(time.time())
    result = await db.payment_transactions.find_one_and_update(
        {"reference": reference},
        {
            "$set": {
                **document,
                "last_updated": now,
            },
            "$setOnInsert": {
                "reference": reference,
                "date_created": now,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return _serialize_payment_doc(result) or {"reference": reference, **document}


async def is_webhook_event_processed(provider: str, event_id: str) -> bool:
    await _ensure_indexes()
    existing = await db.payment_webhook_events.find_one({"provider": provider, "event_id": event_id})
    return existing is not None


async def mark_webhook_event_processed(provider: str, event_id: str) -> bool:
    await _ensure_indexes()
    try:
        await db.payment_webhook_events.insert_one(
            {
                "provider": provider,
                "event_id": event_id,
                "created_at": int(time.time()),
            }
        )
        return True
    except DuplicateKeyError:
        return False
