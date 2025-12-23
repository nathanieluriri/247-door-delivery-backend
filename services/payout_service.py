# ============================================================================
# PAYOUT SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-21 02:16:28 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

from bson import ObjectId
from fastapi import HTTPException
from typing import List

from repositories.payout import (
    create_payout,
    get_payout,
    get_payouts,
    update_payout,
    delete_payout,
)
from schemas.payout import PayoutCreate, PayoutUpdate, PayoutOut


async def add_payout(payout_data: PayoutCreate) -> PayoutOut:
    """adds an entry of PayoutCreate to the database and returns an object

    Returns:
        _type_: PayoutOut
    """
    return await create_payout(payout_data)


async def remove_payout(payout_id: str):
    """deletes a field from the database and removes PayoutCreateobject 

    Raises:
        HTTPException 400: Invalid payout ID format
        HTTPException 404:  Payout not found
    """
    if not ObjectId.is_valid(payout_id):
        raise HTTPException(status_code=400, detail="Invalid payout ID format")

    filter_dict = {"_id": ObjectId(payout_id)}
    result = await delete_payout(filter_dict)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Payout not found")

    else: return True
    
async def retrieve_payout_by_payout_id(id: str,driverId:str) -> PayoutOut:
    """Retrieves payout object based specific Id 

    Raises:
        HTTPException 404(not found): if  Payout not found in the db
        HTTPException 400(bad request): if  Invalid payout ID format

    Returns:
        _type_: PayoutOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid payout ID format")

    filter_dict = {"_id": ObjectId(id),"driverId":driverId}
    result = await get_payout(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Payout not found")

    return result

 

async def retrieve_payouts(driverId:str,start=0,stop=100) -> List[PayoutOut]:
    """Retrieves PayoutOut Objects in a list

    Returns:
        _type_: PayoutOut
    """
    if not ObjectId.is_valid(driverId):
        raise HTTPException(status_code=400, detail="Invalid payout ID format")

    filter_dict = {"driverId":driverId}
    result = await get_payouts(filter_dict,start=start,stop=stop)
    return result


async def update_payout_by_id(payout_id: str, payout_data: PayoutUpdate) -> PayoutOut:
    """updates an entry of payout in the database

    Raises:
        HTTPException 404(not found): if Payout not found or update failed
        HTTPException 400(not found): Invalid payout ID format

    Returns:
        _type_: PayoutOut
    """
    if not ObjectId.is_valid(payout_id):
        raise HTTPException(status_code=400, detail="Invalid payout ID format")

    filter_dict = {"_id": ObjectId(payout_id)}
    result = await update_payout(filter_dict, payout_data)

    if not result:
        raise HTTPException(status_code=404, detail="Payout not found or update failed")

    return result