# ============================================================================
# DRIVER DOCUMENT SCHEMA
# ============================================================================
from __future__ import annotations

import time
from enum import Enum
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, AliasChoices
from bson import ObjectId


class DocumentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DocumentType(str, Enum):
    DRIVER_LICENSE = "driver_license"
    VEHICLE_REGISTRATION = "vehicle_registration"
    INSURANCE = "insurance"
    BACKGROUND_CHECK = "background_check"


class DriverDocumentCreate(BaseModel):
    driverId: str
    documentType: DocumentType
    fileKey: str
    fileName: str
    mimeType: Optional[str] = None
    storageProvider: str = "local"
    signedUrl: Optional[str] = None
    sha256: Optional[str] = None
    md5: Optional[str] = None
    status: DocumentStatus = DocumentStatus.PENDING
    metadata: Dict[str, Any] = Field(default_factory=dict)
    uploadedAt: int = Field(default_factory=lambda: int(time.time()))


class DriverDocumentUpdateStatus(BaseModel):
    status: DocumentStatus
    reason: Optional[str] = None
    lastUpdated: int = Field(default_factory=lambda: int(time.time()))


class DriverDocumentOut(DriverDocumentCreate):
    id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_id", "id"),
        serialization_alias="id",
    )

    @classmethod
    def model_validate_db(cls, doc: dict) -> "DriverDocumentOut":
        if doc and "_id" in doc and isinstance(doc["_id"], ObjectId):
            doc["_id"] = str(doc["_id"])
        return cls.model_validate(doc)


class DriverDocumentsByUser(BaseModel):
    driverId: str
    documents: list[DriverDocumentOut]
