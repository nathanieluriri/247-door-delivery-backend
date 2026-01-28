from pydantic import BaseModel, Field
from typing import Optional

from schemas.imports import AccountStatus, UserType


class UserOut(BaseModel):
    id: str
    email: Optional[str] = None
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    fullName: Optional[str] = Field(default=None, alias="fullName")
    accountStatus: Optional[AccountStatus] = None
    userType: UserType = Field(..., alias="userType")

    model_config = {"populate_by_name": True}
