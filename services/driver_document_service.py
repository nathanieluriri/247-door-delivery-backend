from __future__ import annotations

from typing import List

from repositories.driver_document_repo import (
    create_driver_document,
    list_driver_documents,
    update_driver_document_status,
    get_driver_document,
    get_latest_driver_document_by_type,
    list_pending_documents_by_type,
    list_latest_documents_by_type,
)
from schemas.driver_document import (
    DriverDocumentCreate,
    DriverDocumentOut,
    DriverDocumentUpdateStatus,
    DocumentStatus,
    DocumentType,
    DriverDocumentsByUser,
    DocumentSortBy,
    SortDirection,
)


async def store_driver_document(doc: DriverDocumentCreate) -> DriverDocumentOut:
    return await create_driver_document(doc)


async def get_driver_documents(driver_id: str) -> List[DriverDocumentOut]:
    return await list_driver_documents(driver_id)


async def set_driver_document_status(doc_id: str, update: DriverDocumentUpdateStatus) -> DriverDocumentOut:
    return await update_driver_document_status(doc_id, update)


async def retrieve_driver_document(doc_id: str) -> DriverDocumentOut | None:
    return await get_driver_document(doc_id)


async def get_latest_document_for_driver(
    driver_id: str, document_type: DocumentType, statuses: list[DocumentStatus]
) -> DriverDocumentOut | None:
    return await get_latest_driver_document_by_type(driver_id, document_type, statuses)


async def list_pending_documents_grouped_by_driver(
    document_type: DocumentType,
    driver_id: str | None = None,
    sort_by: DocumentSortBy = DocumentSortBy.uploadedAt,
    sort_dir: SortDirection = SortDirection.desc,
) -> list[DriverDocumentsByUser]:
    raw = await list_pending_documents_by_type(document_type, driver_id, sort_by, sort_dir)
    grouped: list[DriverDocumentsByUser] = []
    for item in raw:
        docs = [DriverDocumentOut.model_validate_db(doc) for doc in item.get("documents", [])]
        grouped.append(DriverDocumentsByUser(driverId=item.get("_id"), documents=docs))
    return grouped


async def list_latest_documents_for_driver(driver_id: str) -> list[DriverDocumentOut]:
    return await list_latest_documents_by_type(driver_id)
