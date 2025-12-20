# ============================================================================
# STRIPE_EVENT SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-14 23:24:53 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

from bson import ObjectId
from fastapi import HTTPException
from typing import List

from repositories.stripe_event import (
    create_stripe_event,
    get_stripe_event,
    get_stripe_events,
    update_stripe_event,
    delete_stripe_event,
)
from schemas.stripe_event import StripeEventCreate, StripeEventUpdate, StripeEventOut


async def add_stripe_event(payload: dict) -> StripeEventOut:
    """adds an entry of StripeEventCreate to the database and returns an object

    Returns:
        _type_: StripeEventOut
    """
    stripe_event_data = StripeEventCreate(**payload)
    event= await create_stripe_event(stripe_event_data)
    return event.model_dump()


async def remove_stripe_event(stripe_event_id: str):
    """deletes a field from the database and removes StripeEventCreateobject 

    Raises:
        HTTPException 400: Invalid stripe_event ID format
        HTTPException 404:  StripeEvent not found
    """
    if not ObjectId.is_valid(stripe_event_id):
        raise HTTPException(status_code=400, detail="Invalid stripe_event ID format while trying to remove stripe event")

    filter_dict = {"_id": ObjectId(stripe_event_id)}
    result = await delete_stripe_event(filter_dict)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="StripeEvent not found")

    else: return True
    
async def retrieve_stripe_event_by_stripe_event_id(id: str) -> StripeEventOut:
    """Retrieves stripe_event object based specific Id 

    Raises:
        HTTPException 404(not found): if  StripeEvent not found in the db
        HTTPException 400(bad request): if  Invalid stripe_event ID format

    Returns:
        _type_: StripeEventOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid stripe_event ID format while trying to retrieve stripe event by stripe event id")

    filter_dict = {"_id": ObjectId(id)}
    result = await get_stripe_event(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="StripeEvent not found")

    return result


async def retrieve_stripe_event_by_stripe_event_id(stripe_id: str) -> StripeEventOut:
    """Retrieves stripe_event object based specific stripe_id 
 

    Returns:
        _type_: StripeEventOut
    """
 
    filter_dict = {"stripe_id": stripe_id}
    result = await get_stripe_event(filter_dict)

    if not result:
        return None

    return result


async def retrieve_stripe_events(start=0,stop=100) -> List[StripeEventOut]:
    """Retrieves StripeEventOut Objects in a list

    Returns:
        _type_: StripeEventOut
    """
    return await get_stripe_events(start=start,stop=stop)


async def update_stripe_event_by_id(stripe_event_id: str, stripe_event_data: StripeEventUpdate) -> StripeEventOut:
    """updates an entry of stripe_event in the database

    Raises:
        HTTPException 404(not found): if StripeEvent not found or update failed
        HTTPException 400(not found): Invalid stripe_event ID format

    Returns:
        _type_: StripeEventOut
    """
    if not ObjectId.is_valid(stripe_event_id):
        raise HTTPException(status_code=400, detail="Invalid stripe_event ID format while trying to update stripe event by id")

    filter_dict = {"_id": ObjectId(stripe_event_id)}
    result = await update_stripe_event(filter_dict, stripe_event_data)

    if not result:
        raise HTTPException(status_code=404, detail="StripeEvent not found or update failed")

    return result