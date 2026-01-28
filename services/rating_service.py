# ============================================================================
# RATING SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-09 09:41:21 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

from bson import ObjectId
from fastapi import HTTPException
from typing import List, Optional

from repositories.rating import (
    create_rating,
    get_rating,
    get_ratings,
    get_user_rating_summary,
    update_rating,
    delete_rating,
)
from services.ride_service import (
    retrieve_ride_by_ride_id
)
from schemas.rating import RatingCreate, RatingSummary, RatingUpdate, RatingOut
from schemas.imports import RideStatus


async def add_rating(rating_data: RatingCreate, driverId: Optional[str] = None, riderId: Optional[str] = None) -> RatingOut:
    """adds an entry of RatingCreate to the database and returns an object

    Returns:
        _type_: RatingOut
    """
   
   
    ride = await retrieve_ride_by_ride_id(id=rating_data.rideId)
    if driverId is not None and riderId is None:
        if ride.rideStatus == RideStatus.completed and ride.driverId == driverId:
            return await create_rating(rating_data)
        raise HTTPException(status_code=403, detail="Driver not allowed to rate this ride")

    if driverId is None and riderId is not None:
        if ride.rideStatus == RideStatus.completed and ride.userId == riderId:
            return await create_rating(rating_data)
        raise HTTPException(status_code=403, detail="Rider not allowed to rate this ride")

    raise HTTPException(status_code=400,detail="Driver Id or Rider Id required for rating ride")

async def remove_rating(rating_id: str):
    """deletes a field from the database and removes RatingCreateobject 

    Raises:
        HTTPException 400: Invalid rating ID format
        HTTPException 404:  Rating not found
    """
    if not ObjectId.is_valid(rating_id):
        raise HTTPException(status_code=400, detail="Invalid rating ID format")

    filter_dict = {"_id": ObjectId(rating_id)}
    result = await delete_rating(filter_dict)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rating not found")

    else: return True
    
async def retrieve_rating_by_rating_id(id: str) -> RatingOut:
    """Retrieves rating object based specific Id 

    Raises:
        HTTPException 404(not found): if  Rating not found in the db
        HTTPException 400(bad request): if  Invalid rating ID format

    Returns:
        _type_: RatingOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid rating ID format")

    filter_dict = {"_id": ObjectId(id)}
    result = await get_rating(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Rating not found")

    return result


async def retrieve_rating_by_user_id(user_id: str) -> RatingSummary:
    """Retrieves rating object based specific Id 

    Raises:
        HTTPException 404(not found): if  Rating not found in the db
        HTTPException 400(bad request): if  Invalid rating ID format

    Returns:
        _type_: RatingOut
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid rating ID format")

    result = await get_user_rating_summary(user_id)

    if not result:
        raise HTTPException(status_code=404, detail="Rating not found")

    return result


async def retrieve_ratings(start=0,stop=100) -> List[RatingOut]:
    """Retrieves RatingOut Objects in a list

    Returns:
        _type_: RatingOut
    """
    return await get_ratings(start=start,stop=stop)


async def update_rating_by_id(rating_id: str, rating_data: RatingUpdate) -> RatingOut:
    """updates an entry of rating in the database

    Raises:
        HTTPException 404(not found): if Rating not found or update failed
        HTTPException 400(not found): Invalid rating ID format

    Returns:
        _type_: RatingOut
    """
    if not ObjectId.is_valid(rating_id):
        raise HTTPException(status_code=400, detail="Invalid rating ID format")

    filter_dict = {"_id": ObjectId(rating_id)}
    result = await update_rating(filter_dict, rating_data)

    if not result:
        raise HTTPException(status_code=404, detail="Rating not found or update failed")

    return result
