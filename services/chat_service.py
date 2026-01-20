# ============================================================================
# CHAT SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-22 11:07:11 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

from bson import ObjectId
from fastapi import HTTPException
from typing import List

from repositories.chat import (
    create_chat,
    get_chat,
    get_chats,
    update_chat,
    delete_chat,
)
from schemas.chat import ChatCreate, ChatUpdate, ChatOut
from schemas.imports import RideStatus
from services.ride_service import retrieve_ride_by_ride_id
from services.sse_service import publish_chat_message
import time


async def add_chat(chat_data: ChatCreate,driverId:str=None,riderId:str=None) -> ChatOut:
    """adds an entry of ChatCreate to the database and returns an object

    Returns:
        _type_: ChatOut
    """
    
   
    ride = await retrieve_ride_by_ride_id(id=chat_data.rideId)
    allowed_status = ride.rideStatus in (
        RideStatus.arrivingToPickup,
        RideStatus.drivingToDestination,
    )
    if driverId is not None and riderId is None:
        if allowed_status and ride.driverId == driverId:
            chat = await create_chat(chat_data)
            await publish_chat_message(
                chat_id=chat.id,
                ride_id=chat.rideId,
                sender_id=chat_data.userId,
                sender_type=chat_data.userType,
                message=chat.text,
                timestamp=int(time.time()),
                rider_id=ride.userId,
                driver_id=ride.driverId,
            )
            return chat
        raise HTTPException(status_code=403, detail="Driver not allowed to chat for this ride")

    if driverId is None and riderId is not None:
        if allowed_status and ride.userId == riderId:
            chat = await create_chat(chat_data)
            await publish_chat_message(
                chat_id=chat.id,
                ride_id=chat.rideId,
                sender_id=chat_data.userId,
                sender_type=chat_data.userType,
                message=chat.text,
                timestamp=int(time.time()),
                rider_id=ride.userId,
                driver_id=ride.driverId,
            )
            return chat
        raise HTTPException(status_code=403, detail="Rider not allowed to chat for this ride")

    raise HTTPException(status_code=400,detail="Driver Id or Rider Id required for creating a chat")


async def remove_chat(chat_id: str):
    """deletes a field from the database and removes ChatCreateobject 

    Raises:
        HTTPException 400: Invalid chat ID format
        HTTPException 404:  Chat not found
    """
    if not ObjectId.is_valid(chat_id):
        raise HTTPException(status_code=400, detail="Invalid chat ID format")

    filter_dict = {"_id": ObjectId(chat_id)}
    result = await delete_chat(filter_dict)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Chat not found")

    else: return True
    
async def retrieve_chat_by_chat_id(id: str) -> List[ChatOut]:
    """Retrieves chat object based specific Id 

    Raises:
        HTTPException 404(not found): if  Chat not found in the db
        HTTPException 400(bad request): if  Invalid chat ID format

    Returns:
        _type_: ChatOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid chat ID format")

    filter_dict = {"rideId": id}
    
    result = await get_chats(filter_dict,start=0,stop=1000)

    if not result:
        raise HTTPException(status_code=404, detail="Chat not found")

    return result


async def retrieve_chats(start=0,stop=100) -> List[ChatOut]:
    """Retrieves ChatOut Objects in a list

    Returns:
        _type_: ChatOut
    """
    return await get_chats(start=start,stop=stop)


async def update_chat_by_id(chat_id: str, chat_data: ChatUpdate) -> ChatOut:
    """updates an entry of chat in the database

    Raises:
        HTTPException 404(not found): if Chat not found or update failed
        HTTPException 400(not found): Invalid chat ID format

    Returns:
        _type_: ChatOut
    """
    if not ObjectId.is_valid(chat_id):
        raise HTTPException(status_code=400, detail="Invalid chat ID format")

    filter_dict = {"_id": ObjectId(chat_id)}
    result = await update_chat(filter_dict, chat_data)

    if not result:
        raise HTTPException(status_code=404, detail="Chat not found or update failed")

    return result
