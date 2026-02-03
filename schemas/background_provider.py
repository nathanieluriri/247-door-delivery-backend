from pydantic import BaseModel, Field
from typing import Optional
from schemas.background_check import BackgroundStatus


class BackgroundProviderPayload(BaseModel):
    provider: str = Field(..., description="Provider name, e.g., checkr")
    status: BackgroundStatus
    referenceId: Optional[str] = None
    notes: Optional[str] = None
    raw: Optional[dict] = None
