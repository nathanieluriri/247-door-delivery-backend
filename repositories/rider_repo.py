
from pymongo import ReturnDocument
from core.database import db
from fastapi import HTTPException,status
from typing import List,Optional
from schemas.rider_schema import RiderUpdate, RiderCreate, RiderOut

async def create_rider(Rider_data: RiderCreate) -> RiderOut:
    Rider_dict = Rider_data.model_dump()
    result =await db.Riders.insert_one(Rider_dict)
    result = await db.Riders.find_one(filter={"_id":result.inserted_id})
  
    returnable_result = RiderOut(**result)
    return returnable_result

async def get_rider(filter_dict: dict) -> Optional[RiderOut]:
    if not filter_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rider filter is required."
        )
    try:
        result = await db.Riders.find_one(filter_dict)

        if result is None:
            return None

        return RiderOut(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching Rider: {str(e)}"
        )
    
async def get_riders(filter_dict: Optional[dict] = None,start=0,stop=100) -> List[RiderOut]:
    try:
        filter_dict = filter_dict or {}
        start = max(0, start or 0)
        if stop is None:
            stop = start + 100
        limit = max(0, stop - start)

        cursor = (db.Riders.find(filter_dict)
        .skip(start)
        .limit(limit)
        )
        Rider_list = []

        async for doc in cursor:
            RiderObj =RiderOut(**doc)
            RiderObj.password=None
            Rider_list.append(RiderObj)

        return Rider_list

    except Exception as e:
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching Riders: {str(e)}"
        )
async def update_rider(filter_dict: dict, Rider_data: RiderUpdate) -> RiderOut:
    if not filter_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rider filter is required."
        )
    update_doc = Rider_data.model_dump(exclude_none=True)
    if not update_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No rider fields to update."
        )
    result = await db.Riders.find_one_and_update(
        filter_dict,
        {"$set": update_doc},
        return_document=ReturnDocument.AFTER
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider not found."
        )
    returnable_result = RiderOut(**result)
    return returnable_result



async def delete_rider(filter_dict: dict):
    if not filter_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rider filter is required."
        )
    result = await db.Riders.delete_one(filter_dict)
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider not found."
        )
    return result
