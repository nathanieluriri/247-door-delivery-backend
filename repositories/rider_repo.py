
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
    
async def get_riders(filter_dict: dict = {},start=0,stop=100) -> List[RiderOut]:
    try:
        if filter_dict is None:
            filter_dict = {}

        cursor = (db.Riders.find(filter_dict)
        .skip(start)
        .limit(stop - start)
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
    result = await db.Riders.find_one_and_update(
        filter_dict,
        {"$set": Rider_data.model_dump()},
        return_document=ReturnDocument.AFTER
    )
    returnable_result = RiderOut(**result)
    return returnable_result



async def delete_rider(filter_dict: dict):
        
    return await db.Riders.delete_one(filter_dict)