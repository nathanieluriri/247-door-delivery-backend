# ============================================================================
#RIDE SCHEMA 
# ============================================================================
# This file was auto-generated on: 2025-12-09 17:57:01 WAT
# It contains Pydantic classes  database
# for managing attributes and validation of data in and out of the MongoDB database.
#
# ============================================================================

from core.routing_config import DeliveryRouteResponse
from core.vehicles_config import VehicleType
from schemas.imports import *
from pydantic import AliasChoices, Field
import time

from schemas.place import Location

class RideBase(BaseModel):
    pickup:str
    destination:str
    stops:Optional[List[str]]=None
    vehicleType:VehicleType
    pickupSchedule:Optional[int]=None
 
class RideCreate(RideBase):
    price:Optional[float]=None
    userId:str
    rideStatus:Optional[RideStatus]=RideStatus.pendingPayment
    origin:Optional[Location]=None
    map: Optional[DeliveryRouteResponse]=None
    paymentStatus:bool = Field(default=False)
    date_created: int = Field(default_factory=lambda: int(time.time()))
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class RideUpdate(BaseModel):
    # Add other fields here
    driverId:Optional[str]=None
    rideStatus:Optional[RideStatus]=None 
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class RideOut(RideBase):
    paymentStatus:bool = Field(default=False)
    price:float
    rideStatus:Optional[RideStatus]=RideStatus.pendingPayment
    driverId:Optional[str]=None
    userId:str
    origin:Location
    paymentLink:Optional[str]=None
    map: DeliveryRouteResponse
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