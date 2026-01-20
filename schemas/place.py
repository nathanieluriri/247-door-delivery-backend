# ============================================================================
#PLACE SCHEMA 
# ============================================================================
# This file was auto-generated on: 2025-12-04 00:54:22 WAT
# It contains Pydantic classes  database
# for managing attributes and validation of data in and out of the MongoDB database.
#
# ============================================================================

from core.routing_config import DeliveryRouteResponse
from core.vehicles import Vehicle
from schemas.imports import *
from pydantic import AliasChoices, Field
import time

class PlaceBase(BaseModel):
    description: str
    name: str
    address: str
    place_id: str
    lat: float
    lng: float

class PlaceDetailsResponse(BaseModel):
    name: str
    address: str
    lat: float
    lng: float

class PlaceCreate(PlaceBase):
    # Add other fields here 
    date_created: int = Field(default_factory=lambda: int(time.time()))
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class PlaceUpdate(BaseModel):
    # Add other fields here 
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class PlaceOut(PlaceBase):
    # Add other fields here 
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
        
        
class Location(BaseModel):
    latitude: float
    longitude: float
    


    
class FareBetweenPlacesCalculationRequest(BaseModel):
    pickup:str
    destination:str
    stops:Optional[List[str]]=None
    
class FareBetweenPlacesCalculationResponse(BaseModel):
    origin:Location
    bike_fare: float
    bike: Vehicle = Field(default_factory=lambda: Vehicle.MOTOR_BIKE.value)
    car_fare: float 
    car: Vehicle = Field(default_factory=lambda: Vehicle.CAR.value)
    map: DeliveryRouteResponse
