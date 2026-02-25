# ============================================================================
#RIDE SCHEMA 
# ============================================================================
# This file was auto-generated on: 2025-12-09 17:57:01 WAT
# It contains Pydantic classes  database
# for managing attributes and validation of data in and out of the MongoDB database.
#
# ============================================================================

from typing import Literal, Union

from core.routing_config import DeliveryRouteResponse
from core.vehicles_config import VehicleType
from schemas.imports import *
from pydantic import AliasChoices, Field
import time
from schemas.place import Location
 

 
 
 

class RidePlace(BaseModel):
    place_id: str
    name: str
    formatted_address: str = Field(
        validation_alias=AliasChoices("formatted_address", "formattedAddress", "address"),
        serialization_alias="formatted_address",
    )
    longitude: float = Field(
        validation_alias=AliasChoices("longitude", "lng"),
        serialization_alias="longitude",
    )
    latitude: float = Field(
        validation_alias=AliasChoices("latitude", "lat"),
        serialization_alias="latitude",
    )


class RideBase(BaseModel):
    pickup: Union[RidePlace, str]
    destination: Union[RidePlace, str]
    stops:Optional[List[str]]=None
    vehicleType:VehicleType
    pickupSchedule:Optional[int]=0
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pickup": {
                        "place_id": "ChIJdd4hrwug2EcRmSrV3Vo6llI",
                        "name": "Downtown Pickup",
                        "formatted_address": "123 Main St, City",
                        "longitude": 3.4219,
                        "latitude": 6.455,
                    },
                    "destination": {
                        "place_id": "ChIJFfyz7Qug2EcRkzTg3u8g9a4",
                        "name": "Airport Dropoff",
                        "formatted_address": "Airport Rd, City",
                        "longitude": 3.3569,
                        "latitude": 6.5776,
                    },
                    "stops": ["ChIJn8G1vQug2EcR0T9k0vJdp0E"],
                    "vehicleType": "CAR",
                    "pickupSchedule": 0,
                }
            ]
        }
    }
 
class RideCreate(RideBase):
    price:Optional[float]=None
    userId:str
    rideStatus:Optional[RideStatus]=RideStatus.matching
    origin:Optional[Location]=None
    map: Optional[DeliveryRouteResponse]=None
    paymentStatus:bool = Field(default=False)
    isScheduled: bool = False
    scheduledPickupAtMs: Optional[int] = None
    dispatchStartAtMs: Optional[int] = None
    noDriverPromptedAtMs: Optional[int] = None
    noDriverDecision: Optional[str] = None
    noDriverDecisionDeadlineMs: Optional[int] = None
    paymentDueAtMs: Optional[int] = None
    paymentAttempts: int = 0
    cancelReason: Optional[str] = None
    date_created: int = Field(default_factory=lambda: int(time.time()))
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class RideUpdate(BaseModel):
    # Add other fields here
    paymentLink:Optional[str]=None
    invoiceData:Optional[InvoiceData]=None
    paymentStatus:Optional[bool]=None 
    checkoutSessionObject:Optional[CheckoutSessionObject]=None
    stripeEvent:Optional[StripeEvent]=None
    driverId:Optional[str]=None
    rideStatus:Optional[RideStatus]=None
    isScheduled: Optional[bool] = None
    scheduledPickupAtMs: Optional[int] = None
    dispatchStartAtMs: Optional[int] = None
    noDriverPromptedAtMs: Optional[int] = None
    noDriverDecision: Optional[str] = None
    noDriverDecisionDeadlineMs: Optional[int] = None
    paymentDueAtMs: Optional[int] = None
    paymentAttempts: Optional[int] = None
    cancelReason: Optional[str] = None
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class RideOut(RideBase):

    paymentStatus:bool = Field(default=False)
    price: Optional[float] = None
    rideStatus:Optional[RideStatus]=RideStatus.matching
    driverId:Optional[str]=None
    userId:str
    invoiceData:Optional[InvoiceData]=None
    checkoutSessionObject:Optional[CheckoutSessionObject]=None
    stripeEvent:Optional[StripeEvent]=None
    isScheduled: bool = False
    scheduledPickupAtMs: Optional[int] = None
    dispatchStartAtMs: Optional[int] = None
    noDriverPromptedAtMs: Optional[int] = None
    noDriverDecision: Optional[str] = None
    noDriverDecisionDeadlineMs: Optional[int] = None
    paymentDueAtMs: Optional[int] = None
    paymentAttempts: int = 0
    cancelReason: Optional[str] = None
    origin: Optional[Location] = None
    paymentLink:Optional[str]=None
    map: Optional[DeliveryRouteResponse] = None
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


class RideShareLinkOut(BaseModel):
    shareId: str
    shareLink: str
    rideId: str


class NoDriverDecisionIn(BaseModel):
    decision: Literal["keep_searching", "cancel_ride"]
