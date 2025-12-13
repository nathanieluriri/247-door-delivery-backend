# ============================================================================
# ADDRESS SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-09 12:56:27 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

from bson import ObjectId
from fastapi import HTTPException
from typing import List

from repositories.address import (
    create_address,
    get_address,
    get_addresss,
    update_address,
    delete_address,
)
from schemas.address import AddressCreate, AddressUpdate, AddressOut


async def add_address(address_data: AddressCreate) -> AddressOut:
    """adds an entry of AddressCreate to the database and returns an object

    Returns:
        _type_: AddressOut
    """
    return await create_address(address_data)


async def remove_address(address_id: str,user_id:str):
    """deletes a field from the database and removes AddressCreateobject 

    Raises:
        HTTPException 400: Invalid address ID format
        HTTPException 404:  Address not found
    """
    if not ObjectId.is_valid(address_id):
        raise HTTPException(status_code=400, detail="Invalid address ID format")
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    filter_dict = {"_id": ObjectId(address_id),"userId":user_id}
    result = await delete_address(filter_dict)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Address not found")

    else: return True
    
async def retrieve_address_by_address_id(id: str) -> AddressOut:
    """Retrieves address object based specific Id 

    Raises:
        HTTPException 404(not found): if  Address not found in the db
        HTTPException 400(bad request): if  Invalid address ID format

    Returns:
        _type_: AddressOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid address ID format")

    filter_dict = {"_id": ObjectId(id)}
    result = await get_address(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Address not found")

    return result


  
async def retrieve_address_by_user_id(userId: str) -> List[AddressOut]:
    """Retrieves address object based specific Id 

    Raises:
        HTTPException 404(not found): if  Address not found in the db
        HTTPException 400(bad request): if  Invalid address ID format

    Returns:
        _type_: AddressOut
    """
    if not ObjectId.is_valid(userId):
        raise HTTPException(status_code=400, detail="Invalid address ID format")

    filter_dict = {"userId": userId}
    result = await get_addresss(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Address not found")

    return result


async def retrieve_addresss(start=0,stop=100) -> List[AddressOut]:
    """Retrieves AddressOut Objects in a list

    Returns:
        _type_: AddressOut
    """
    return await get_addresss(start=start,stop=stop)


async def update_address_by_id(address_id: str, address_data: AddressUpdate,user_id:str) -> AddressOut:
    """updates an entry of address in the database

    Raises:
        HTTPException 404(not found): if Address not found or update failed
        HTTPException 400(not found): Invalid address ID format

    Returns:
        _type_: AddressOut
    """
    if not ObjectId.is_valid(address_id):
        raise HTTPException(status_code=400, detail="Invalid address ID format")
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    filter_dict = {"_id": ObjectId(address_id),"userId":user_id}
    result = await update_address(filter_dict, address_data)

    if not result:
        raise HTTPException(status_code=404, detail="Address not found or update failed")

    return result