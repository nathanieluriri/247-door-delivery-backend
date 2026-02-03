# ============================================================================
#DRIVER SCHEMA 
# ============================================================================
# This file was auto-generated on: 2025-12-03 10:19:19 WAT
# It contains Pydantic classes  database
# for managing attributes and validation of data in and out of the MongoDB database.
#
# ============================================================================

import os
import time
from schemas.imports import *
from core.vehicles_config import VehicleType
from pydantic import AliasChoices, Field, field_validator

from security.hash import hash_password

VEHICLE_MIN_YEAR = int(os.getenv("DRIVER_VEHICLE_MIN_YEAR", "2002"))
VEHICLE_MAX_YEAR = int(os.getenv("DRIVER_VEHICLE_MAX_YEAR", str(time.gmtime().tm_year)))

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
class DriverUpdateProfile(BaseModel):
    # Add other fields here 
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    
class DriverUpdate(BaseModel):
    # Add other fields here 
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    stripeAccountId: Optional[str] = None
    payoutsEnabled: Optional[bool] = None
    chargesEnabled: Optional[bool] = None
    detailsSubmitted: Optional[bool] = None
    requirementsCurrentlyDue: Optional[List[str]] = None
    requirementsEventuallyDue: Optional[List[str]] = None
    requirementsPendingVerification: Optional[List[str]] = None
    onboardingRefreshUrl: Optional[str] = None
    onboardingReturnUrl: Optional[str] = None
    accountStatus:Optional[AccountStatus]=None
    last_updated: int = Field(default_factory=lambda: int(time.time()))
   
class DriverUpdateStripeAccountId(BaseModel):
    # Add other fields here 
    stripeAccountId: Optional[str] = None
    payoutsEnabled: Optional[bool] = None
    chargesEnabled: Optional[bool] = None
    detailsSubmitted: Optional[bool] = None
    requirementsCurrentlyDue: Optional[List[str]] = None
    requirementsEventuallyDue: Optional[List[str]] = None
    requirementsPendingVerification: Optional[List[str]] = None
    onboardingRefreshUrl: Optional[str] = None
    onboardingReturnUrl: Optional[str] = None
    
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
    payoutsEnabled: Optional[bool] = None
    chargesEnabled: Optional[bool] = None
    detailsSubmitted: Optional[bool] = None
    requirementsCurrentlyDue: Optional[List[str]] = None
    requirementsEventuallyDue: Optional[List[str]] = None
    requirementsPendingVerification: Optional[List[str]] = None
    onboardingRefreshUrl: Optional[str] = None
    onboardingReturnUrl: Optional[str] = None
    vehicleType: Optional[VehicleType] = None
    vehicleMake: Optional[str] = None
    vehicleModel: Optional[str] = None
    vehicleColor: Optional[str] = None
    vehiclePlateNumber: Optional[str] = None
    vehicleYear: Optional[int] = None
    profileComplete: bool = Field(default=False, alias="profileComplete")
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

    @model_validator(mode="after")
    def set_profile_complete(self):
        required_fields = [
            self.vehicleType,
            self.vehicleMake,
            self.vehicleModel,
            self.vehicleColor,
            self.vehiclePlateNumber,
            self.vehicleYear,
        ]
        self.profileComplete = all(field is not None and str(field).strip() for field in required_fields)
        return self
            
    class Config:
        populate_by_name = True  # allows using `id` when constructing the model
        arbitrary_types_allowed = True  # allows ObjectId type
        json_encoders ={
            ObjectId: str  # automatically converts ObjectId → str
        }


class DriverLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    accuracy_m: Optional[float] = None
    timestamp: int = Field(default_factory=lambda: int(time.time()))


class DriverVehicleUpdate(BaseModel):
    vehicleType: VehicleType
    vehicleMake: str
    vehicleModel: str
    vehicleColor: str
    vehiclePlateNumber: str
    vehicleYear: int
    last_updated: int = Field(default_factory=lambda: int(time.time()))

    @field_validator("vehicleMake", "vehicleModel", "vehicleColor")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Field must be at least 2 characters")
        if len(value) > 50:
            raise ValueError("Field must be 50 characters or fewer")
        return value

    @field_validator("vehiclePlateNumber")
    @classmethod
    def validate_plate_number(cls, value: str) -> str:
        value = value.strip().upper()
        if len(value) < 4 or len(value) > 12:
            raise ValueError("Plate number must be between 4 and 12 characters")
        for ch in value:
            if not (ch.isalnum() or ch == "-"):
                raise ValueError("Plate number may only contain letters, numbers, and '-'")
        return value

    @field_validator("vehicleYear")
    @classmethod
    def validate_vehicle_year(cls, value: int) -> int:
        if value < VEHICLE_MIN_YEAR:
            raise ValueError(f"Vehicle year must be >= {VEHICLE_MIN_YEAR}")
        if value > VEHICLE_MAX_YEAR:
            raise ValueError(f"Vehicle year must be <= {VEHICLE_MAX_YEAR}")
        return value
        
        
        
        
        
