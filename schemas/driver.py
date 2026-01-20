# ============================================================================
#DRIVER SCHEMA 
# ============================================================================
# This file was auto-generated on: 2025-12-03 10:19:19 WAT
# It contains Pydantic classes  database
# for managing attributes and validation of data in and out of the MongoDB database.
#
# ============================================================================

from schemas.imports import *
from pydantic import AliasChoices, Field
import time

from security.hash import hash_password

class DriverBase(BaseModel):
    # Add other fields here 
    email:EmailStr
    password:str | bytes

class DriverCreate(DriverBase):
    # Add other fields here
    firstName:Optional[str]=''
    lastName:Optional[str]='' 
    accountStatus:Optional[AccountStatus]=AccountStatus.PENDING_VERIFICATION
    date_created: int = Field(default_factory=lambda: int(time.time()))
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    @model_validator(mode='after')
    def obscure_password(self):
        self.password=hash_password(self.password)
        self.email = self.email.lower()
        return self
    
    
class DriverRefresh(BaseModel):
    # Add other fields here 
    refresh_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("refresh_token", "refreshToken"),
        serialization_alias="refreshToken",
    )
    pass

class DriverUpdate(BaseModel):
    # Add other fields here 
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    
    last_updated: int = Field(default_factory=lambda: int(time.time()))
   
class DriverUpdateStripeAccountId(BaseModel):
    # Add other fields here 
    stripeAccountId: Optional[str] = None
    
    last_updated: int = Field(default_factory=lambda: int(time.time()))
   
class DriverUpdatePassword(BaseModel):
    # Add other fields here 
    password:Optional[str | bytes]=None
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    @model_validator(mode='after')
    def obscure_password(self):
        if self.password:
            self.password=hash_password(self.password)
        return self
        
        

        
class DriverUpdateAccountStatus(BaseModel):
    accountStatus:AccountStatus
    last_updated: int = Field(default_factory=lambda: int(time.time()))
    
    

class DriverOut(DriverBase):
    # Add other fields here 
    firstName:Optional[str]=''
    lastName:Optional[str]=''     
    stripeAccountId: Optional[str] = None
    accountStatus:Optional[AccountStatus]=AccountStatus.PENDING_VERIFICATION
    id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_id", "id"),
        serialization_alias="id",
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
        
        
        
        
        
