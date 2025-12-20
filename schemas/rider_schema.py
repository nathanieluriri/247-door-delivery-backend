from schemas.imports import *
from pydantic import Field
import time
from security.hash import hash_password
class RiderBase(BaseModel):
    # Add other fields here
    firstName:Optional[str]=''
    lastName:Optional[str ]=''
    email:EmailStr
    password:str | bytes
    loginType:Optional[LoginType]=LoginType.password
    pass

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
    firstName:str
    lastName:str 
    last_updated: int = Field(default_factory=lambda: int(time.time()))
   
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
    accountStatus:Optional[AccountStatus]=AccountStatus.PENDING_VERIFICATION
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
            
    class Config:
        populate_by_name = True  # allows using `id` when constructing the model
        arbitrary_types_allowed = True  # allows ObjectId type
        json_encoders = {
            ObjectId: str  # automatically converts ObjectId → str
        }