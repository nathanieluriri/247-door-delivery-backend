# ============================================================================
# RIDE SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-09 17:57:17 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

from bson import ObjectId
from fastapi import Depends, HTTPException
from typing import List

from core.payements import PaymentService, get_payment_service
from repositories.ride import (
    create_ride,
    get_ride,
    get_rides,
    update_ride,
    delete_ride,
)
from schemas.imports import RideStatus
from schemas.ride import RideCreate, RideUpdate, RideOut


async def add_ride(
    ride_data: RideCreate,
    payment_service: PaymentService = Depends(get_payment_service)
) -> RideOut:
    """Adds an entry of RideCreate to the database and returns an object."""
    # TODO: DON'T ALLOW USER'S CREATE NEW RIDES IF OLD ONE'S HAVEN'T BEEN CLEARED YET ELSE THERE WILL BE MANY PENDING PAYMENT RIDES ON THE HISTORY THE RIDE SHOULD BE CANCELED OR... COMPLETED
    # TODO: MAKE A CASE WHERE THE RIDE GETS DELETED IF ITS PENDING PAYMENT FOR 240 SECONDS 
    # TODO: AUTOMATICALLY CANCEL  A RIDE IF NO DRIVER HAS PICKED IN 300 SECONDS SO USER CAN BOOK A AGAIN OR CHANGE LOCATION 
    
 
    ride = await create_ride(ride_data)
    payment = await payment_service.create_payment_link(ride_id=ride.id)
    ride.paymentLink= payment
    
    return ride


async def remove_ride(ride_id: str):
    """deletes a field from the database and removes RideCreateobject 

    Raises:
        HTTPException 400: Invalid ride ID format
        HTTPException 404:  Ride not found
    """
    if not ObjectId.is_valid(ride_id):
        raise HTTPException(status_code=400, detail="Invalid ride ID format")

    filter_dict = {"_id": ObjectId(ride_id)}
    result = await delete_ride(filter_dict)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ride not found")

    else: return True
    
async def retrieve_ride_by_ride_id(id: str) -> RideOut:
    """Retrieves ride object based specific Id 

    Raises:
        HTTPException 404(not found): if  Ride not found in the db
        HTTPException 400(bad request): if  Invalid ride ID format

    Returns:
        _type_: RideOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid ride ID format")

    filter_dict = {"_id": ObjectId(id)}
    result = await get_ride(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Ride not found")

    return result



async def retrieve_ride_by_user_id(user_id: str) -> RideOut:
    """Retrieves ride object based specific Id 

    Raises:
        HTTPException 404(not found): if  Ride not found in the db
        HTTPException 400(bad request): if  Invalid ride ID format

    Returns:
        _type_: RideOut
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid ride ID format")

    filter_dict = {"userId": user_id}
    result = await get_rides(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Ride not found")

    return result



async def retrieve_ride_by_user_id_and_ride_id(user_id: str,ride_id:str) -> RideOut:
    """Retrieves ride object based specific Id 

    Raises:
        HTTPException 404(not found): if  Ride not found in the db
        HTTPException 400(bad request): if  Invalid ride ID format

    Returns:
        _type_: RideOut
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid ride ID format")

    if not ObjectId.is_valid(ride_id):
        raise HTTPException(status_code=400, detail="Invalid ride ID format")

    filter_dict = {"userId": user_id,"_id":ObjectId(ride_id)}
    result = await get_ride(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Ride not found")

    return result


async def retrieve_rides(start=0,stop=100) -> List[RideOut]:
    """Retrieves RideOut Objects in a list

    Returns:
        _type_: RideOut
    """
    return await get_rides(start=start,stop=stop)


async def update_ride_by_id(ride_id: str, ride_data: RideUpdate,rider_id:str=None,driver_id:str=None) -> RideOut:
    # TODO: ADD MORE CASES RIGHT NOW THE ONLY UPDATE THAT CAN WORK IS WHEN A RIDE IS BEING CANCELLED
    """updates an entry of ride in the database

    Raises:
        HTTPException 404(not found): if Ride not found or update failed
        HTTPException 400(not found): Invalid ride ID format

    Returns:
        _type_: RideOut
    """
    filter_dict={}
    if not ObjectId.is_valid(ride_id):
        raise HTTPException(status_code=400, detail="Invalid ride ID format")
    
    ride = await retrieve_ride_by_ride_id(id=ride_id)
    
    
    if rider_id!=None:
        
        filter_dict["userId"]=rider_id
    
    if driver_id!=None:
        filter_dict["driverId"]=driver_id
    
    filter_dict["_id"] = ObjectId(ride_id)
    
    if (ride.rideStatus==RideStatus.findingDriver or ride.rideStatus==RideStatus.pendingPayment) and (ride_data.rideStatus==RideStatus.canceled):
        # Only case that allows the ride to be canceled
        result = await update_ride(filter_dict, ride_data)

    if not result:
        raise HTTPException(status_code=404, detail="Ride not found or update failed")
    
    
        
    return result