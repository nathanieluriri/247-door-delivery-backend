import re

from schemas.imports import *
from pydantic import Field, field_validator
import time
from security.hash import hash_password

PHONE_NUMBER_PATTERN = re.compile(r"^[0-9+()\- ]{7,20}$")


def _normalize_phone_number(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Phone number is required")
    if not PHONE_NUMBER_PATTERN.fullmatch(normalized):
        raise ValueError("Phone number format is invalid")
    return normalized

class RiderBase(BaseModel):
    # Add other fields here
    firstName:Optional[str]=''
    lastName:Optional[str ]=''
    email:EmailStr
    password:str | bytes
    loginType:Optional[LoginType]=LoginType.password
    phoneNumber: Optional[str] = None
    pass
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "firstName": "Taylor",
                    "lastName": "Jordan",
                    "email": "rider@example.com",
                    "password": "StrongPass123!",
                    "loginType": "password",
                }
            ]
        }
    }

    @field_validator("phoneNumber")
    @classmethod
    def validate_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_phone_number(value)

class RiderRefresh(BaseModel):
    # Add other fields here 
    refresh_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("refresh_token", "refreshToken"),
        serialization_alias="refreshToken",
    )
  

class RiderCreate(RiderBase):
    # Add other fields here
 
    accountStatus:Optional[AccountStatus]=AccountStatus.ACTIVE
 
    date_created: int = Field(default_factory=lambda: int(time.time()))
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    @model_validator(mode='after')
    def obscure_password(self):
        self.password=hash_password(self.password)
        self.email = self.email.lower()
        return self
    
    
class RiderUpdate(BaseModel):
    # Add other fields here 
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    phoneNumber: Optional[str] = None
    last_updated: int = Field(default_factory=lambda: int(time.time()))

    @field_validator("phoneNumber")
    @classmethod
    def validate_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_phone_number(value)


class RiderPhoneUpdate(BaseModel):
    phoneNumber: str
    last_updated: int = Field(default_factory=lambda: int(time.time()))

    @field_validator("phoneNumber")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        return _normalize_phone_number(value)
   
class RiderUpdatePassword(BaseModel):
    # Add other fields here 
    password:Optional[str | bytes]=None
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    @model_validator(mode='after')
    def obscure_password(self):
        if self.password:
            self.password=hash_password(self.password)
        return self
        
class RiderUpdateAccountStatus(BaseModel):
    accountStatus:AccountStatus
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    

class RiderOut(RiderBase):
    # Add other fields here 
    firstName:Optional[str]=''
    lastName:Optional[str]='' 
    phoneNumber: Optional[str] = None
    accountStatus:Optional[AccountStatus]=AccountStatus.ACTIVE
    id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_id", "id"),
        serialization_alias="id",
    )
   
    date_created: Optional[int] = None
    last_updated: Optional[int] = None
    refresh_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("refresh_token", "refreshToken"),
        serialization_alias="refreshToken",
    )
    access_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("access_token", "accessToken"),
        serialization_alias="accessToken",
    )
    @model_validator(mode="before")
    @classmethod
    def convert_objectid(cls, values):
        if "_id" in values and isinstance(values["_id"], ObjectId):
            values["_id"] = str(values["_id"])  # coerce to string before validation
        return values
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
    )
