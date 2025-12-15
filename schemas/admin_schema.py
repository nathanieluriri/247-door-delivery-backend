from schemas.imports import *
from pydantic import Field
import time
from security.hash import hash_password
from typing import List, Optional
from pydantic import BaseModel, EmailStr, model_validator

from security.permissions import default_get_permissions, default_permissions 




class AdminBase(BaseModel):

    full_name: str
    email: EmailStr
    password: str | bytes
    permissionList: Optional[PermissionList] = Field(
    default_factory=default_get_permissions
)

class AdminLogin(BaseModel):
    # Add other fields here 
    email:EmailStr
    password:str | bytes
    pass
class AdminRefresh(BaseModel):
    # Add other fields here 
    refresh_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("refresh_token", "refreshToken"),
        serialization_alias="refreshToken",
    )
    pass


class AdminCreate(AdminBase):
    # Add other fields here
    invited_by:str 
    date_created: int = Field(default_factory=lambda: int(time.time()))
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    @model_validator(mode='after')
    def obscure_password(self):
        self.password=hash_password(self.password)
        return self
    
    
class AdminUpdate(BaseModel):
    # Add other fields here 
    full_name:str
    last_updated: int = Field(default_factory=lambda: int(time.time()))
   
class AdminUpdatePassword(BaseModel):
    # Add other fields here 
    password:Optional[str | bytes]=None
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    @model_validator(mode='after')
    def obscure_password(self):
        if self.password:
            self.password=hash_password(self.password)
            return self
        
class AdminUpdateAccountStatus(BaseModel):
    accountStatus:AccountStatus
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    
    
class AdminOut(AdminBase):
    full_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("full_name", "fullName"),
        serialization_alias="fullName",
    ) 
 
    accountStatus:Optional[AccountStatus]=AccountStatus.ACTIVE
    id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_id", "id"),
        serialization_alias="id",
    )
    permissionList: Optional[PermissionList] = Field(
    default_factory=default_permissions
)
  
    invited_by: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("invited_by", "invitedBy"),
        serialization_alias="invitedBy",
    )
    date_created: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("date_created", "dateCreated"),
        serialization_alias="dateCreated",
    )
    last_updated: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("last_updated", "lastUpdated"),
        serialization_alias="lastUpdated",
    )
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
            
    class Config:
        populate_by_name = True  # allows using `id` when constructing the model
        arbitrary_types_allowed = True  # allows ObjectId type
        json_encoders ={
            ObjectId: str  # automatically converts ObjectId → str
        }