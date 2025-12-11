# ============================================================================
# RATING SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-09 09:41:21 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

from bson import ObjectId
from fastapi import HTTPException
from typing import List

from repositories.rating import (
    create_rating,
    get_rating,
    get_ratings,
    get_user_rating_summary,
    update_rating,
    delete_rating,
)
from schemas.rating import RatingCreate, RatingUpdate, RatingOut


async def add_rating(rating_data: RatingCreate) -> RatingOut:
    """adds an entry of RatingCreate to the database and returns an object

    Returns:
        _type_: RatingOut
    """
    return await create_rating(rating_data)


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


async def retrieve_rating_by_user_id(user_id: str) -> RatingOut:
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