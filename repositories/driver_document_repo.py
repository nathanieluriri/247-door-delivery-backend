from __future__ import annotations

from typing import List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo import ReturnDocument

from core.database import db
from schemas.driver_document import (
    DriverDocumentCreate,
    DriverDocumentOut,
    DriverDocumentUpdateStatus,
    DocumentStatus,
    DocumentType,
)


async def create_driver_document(doc: DriverDocumentCreate) -> DriverDocumentOut:
    payload = doc.model_dump()
    result = await db.driver_documents.insert_one(payload)
    created = await db.driver_documents.find_one({"_id": result.inserted_id})
    return DriverDocumentOut.model_validate_db(created)


async def list_driver_documents(driver_id: str) -> List[DriverDocumentOut]:
    cursor = db.driver_documents.find({"driverId": driver_id}).sort("uploadedAt", -1)
    docs: List[DriverDocumentOut] = []
    async for item in cursor:
        docs.append(DriverDocumentOut.model_validate_db(item))
    return docs


async def update_driver_document_status(
    doc_id: str, update: DriverDocumentUpdateStatus
) -> DriverDocumentOut:
    if not ObjectId.is_valid(doc_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document id")

    update_doc = update.model_dump(exclude_none=True)
    updated = await db.driver_documents.find_one_and_update(
        {"_id": ObjectId(doc_id)},
        {"$set": update_doc},
        return_document=ReturnDocument.AFTER,
    )

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver document not found")

    return DriverDocumentOut.model_validate_db(updated)


async def get_driver_document(doc_id: str) -> Optional[DriverDocumentOut]:
    if not ObjectId.is_valid(doc_id):
        return None
    doc = await db.driver_documents.find_one({"_id": ObjectId(doc_id)})
    if not doc:
        return None
    return DriverDocumentOut.model_validate_db(doc)


async def get_latest_driver_document_by_type(
    driver_id: str, document_type: DocumentType, statuses: list[DocumentStatus]
) -> Optional[DriverDocumentOut]:
    doc = await db.driver_documents.find_one(
        {"driverId": driver_id, "documentType": document_type, "status": {"$in": statuses}},
        sort=[("uploadedAt", -1)],
    )
    if not doc:
        return None
    return DriverDocumentOut.model_validate_db(doc)


async def list_pending_documents_by_type(document_type: DocumentType) -> list[dict]:
    pipeline = [
        {"$match": {"documentType": document_type, "status": DocumentStatus.PENDING}},
        {"$sort": {"uploadedAt": -1}},
        {
            "$group": {
                "_id": "$driverId",
                "documents": {"$push": "$$ROOT"},
            }
        },
    ]
    cursor = db.driver_documents.aggregate(pipeline)
    results: list[dict] = []
    async for item in cursor:
        results.append(item)
    return results
