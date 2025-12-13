# ============================================================================
#RATING SCHEMA 
# ============================================================================
# This file was auto-generated on: 2025-12-09 09:41:07 WAT
# It contains Pydantic classes  database
# for managing attributes and validation of data in and out of the MongoDB database.
#
# ============================================================================

from schemas.imports import *
from pydantic import AliasChoices, Field
import time

class RatingBase(BaseModel):
    rideId: str
    userId: str     #  the user who is being rated
    rating: int = Field(..., ge=1, le=5)

class RatingCreate(RatingBase):
    # Add other fields here
    raterId: str 
    date_created: int = Field(default_factory=lambda: int(time.time()))
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class RatingUpdate(BaseModel):
    # Add other fields here 
    last_updated: int = Field(default_factory=lambda: int(time.time()))

class RatingOut(RatingBase):
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
        
        
        
        
class RatingSummary(BaseModel):
    avgRating: float
    totalRides: int