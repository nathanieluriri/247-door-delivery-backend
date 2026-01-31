from __future__ import annotations

from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException

from core.database import db
from schemas.driver_document import (
    DriverDocumentCreate,
    DriverDocumentOut,
    DriverDocumentUpdateStatus,
)


async def create_driver_document(doc: DriverDocumentCreate) -> DriverDocumentOut:
    payload = doc.model_dump()
    result = await db.driver_documents.insert_one(payload)
    created = await db.driver_documents.find_one({"_id": result.inserted_id})
    return DriverDocumentOut.model_validate_db(created)


async def list_driver_documents(driver_id: str) -> List[DriverDocumentOut]:
    cursor = db.driver_documents.find({"driverId": driver_id}).sort("uploadedAt", -1)
    docs: list[DriverDocumentOut] = []
    async for doc in cursor:
        docs.append(DriverDocumentOut.model_validate_db(doc))
    return docs


async def update_driver_document_status(doc_id: str, update: DriverDocumentUpdateStatus) -> DriverDocumentOut:
    if not ObjectId.is_valid(doc_id):
        raise HTTPException(status_code=400, detail="Invalid document id")

    result = await db.driver_documents.find_one_and_update(
        {"_id": ObjectId(doc_id)},
        {"$set": update.model_dump(exclude_none=True)},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    return DriverDocumentOut.model_validate_db(result)
