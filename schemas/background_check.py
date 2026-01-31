from __future__ import annotations

import time
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, AliasChoices
from bson import ObjectId


class BackgroundStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


class BackgroundCheckCreate(BaseModel):
    driverId: str
    status: BackgroundStatus = BackgroundStatus.PENDING
    provider: Optional[str] = None
    referenceId: Optional[str] = None
    notes: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updatedAt: int = Field(default_factory=lambda: int(time.time()))


class BackgroundCheckUpdate(BaseModel):
    status: BackgroundStatus
    notes: Optional[str] = None
    referenceId: Optional[str] = None
    updatedAt: int = Field(default_factory=lambda: int(time.time()))


class BackgroundCheckOut(BackgroundCheckCreate):
    id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_id", "id"),
        serialization_alias="id",
    )

    @classmethod
    def model_validate_db(cls, doc: dict) -> "BackgroundCheckOut":
        if doc and "_id" in doc and isinstance(doc["_id"], ObjectId):
            doc["_id"] = str(doc["_id"])
        return cls.model_validate(doc)
