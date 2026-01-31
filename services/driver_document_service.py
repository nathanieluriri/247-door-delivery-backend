from __future__ import annotations

from typing import List

from repositories.driver_document_repo import (
    create_driver_document,
    list_driver_documents,
    update_driver_document_status,
)
from schemas.driver_document import (
    DriverDocumentCreate,
    DriverDocumentOut,
    DriverDocumentUpdateStatus,
)


async def store_driver_document(doc: DriverDocumentCreate) -> DriverDocumentOut:
    return await create_driver_document(doc)


async def get_driver_documents(driver_id: str) -> List[DriverDocumentOut]:
    return await list_driver_documents(driver_id)


async def set_driver_document_status(doc_id: str, update: DriverDocumentUpdateStatus) -> DriverDocumentOut:
    return await update_driver_document_status(doc_id, update)
