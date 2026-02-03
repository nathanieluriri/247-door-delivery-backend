# ============================================================================
# STORAGE UPLOAD SCHEMA
# ============================================================================

from pydantic import BaseModel, Field
from typing import Optional


class CloudflareUploadResponse(BaseModel):
    key: str
    provider: str
    signedUrl: Optional[str] = Field(default=None, alias="signedUrl")
    sha256: Optional[str] = None
    md5: Optional[str] = None
    sizeBytes: int = Field(..., alias="sizeBytes")
    contentType: Optional[str] = Field(default=None, alias="contentType")
    filename: str

    model_config = {"populate_by_name": True}
