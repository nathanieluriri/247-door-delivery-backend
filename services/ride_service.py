# ============================================================================
# RIDE SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-09 17:57:17 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

import os
import time
import uuid
from decimal import Decimal
from core.scheduler import scheduler
from fastapi import status
from bson import ObjectId
from fastapi import Depends, HTTPException
from typing import List
from datetime import datetime, timedelta
from datetime import timezone
utc = timezone.utc
from core.payments import PaymentService, get_payment_service
from services.sse_service import publish_ride_status_update, publish_ride_request
from core.redis_cache import async_redis
from repositories.ride import (
    check_if_user_has_an_existing_active_ride,
    create_ride,
    get_ride,
    get_rides,
    update_ride,
    delete_ride,
)
from schemas.imports import ALLOWED_RIDE_STATUS_TRANSITIONS, RIDE_REFUND_RULES, RideStatus
from schemas.ride import RideCreate, RideUpdate, RideOut, RideShareLinkOut


FRONTEND_SHARE_RIDE_URL = os.getenv("FRONTEND_SHARE_RIDE_URL", "http://localhost:8080/share/ride")


async def check_if_state_is_still_pending_payment_and_delete_ride_if_it_is_still_pending_payment(ride_id:str):
    from celery_worker import celery_app
    print("Currently running the scheduled task check if state still pending payment")
    filter_dict = {"_id": ObjectId(ride_id)}
    ride =await get_ride(filter_dict=filter_dict)
   
    if ride:
        if (ride.rideStatus==RideStatus.pendingPayment) and (ride.paymentStatus==False):
            if ride.last_updated is None:
                return
            if time.time() - ride.last_updated >= 200:
              
                celery_app.send_task(
                "celery_worker.run_async_task",
                args=[
                    "delete_ride",       # function path
                    {"ride_id": ride_id} # kwargs
                        ]
                    )
            else:
                run_time = datetime.now(utc) + timedelta(seconds=240)
                scheduler.add_job(
                check_if_state_is_still_pending_payment_and_delete_ride_if_it_is_still_pending_payment,
                trigger="date",run_date=run_time, kwargs={ "ride_id": ride.id },misfire_grace_time=31536000
                )
                pass
        
async def check_if_state_is_still_finding_driver_and_6_mins_have_passed_if_so_delete_the_ride(ride_id:str):
    from celery_worker import celery_app
    filter_dict = {"_id": ObjectId(ride_id)}
    print("Currently running the scheduled task check if state still finding driver")
    ride =await get_ride(filter_dict=filter_dict)
    if ride:
        if (ride.rideStatus==RideStatus.findingDriver):
            if ride.last_updated is None:
                return
            if time.time() - ride.last_updated >= 300:
                celery_app.send_task(
                "celery_worker.run_async_task",
                args=[
                    "delete_ride",       # function path
                    {"ride_id": ride_id} # kwargs
                        ]
                    )
            else:
                run_time = datetime.now(utc) + timedelta(seconds=240)
                scheduler.add_job(
                check_if_state_is_still_finding_driver_and_6_mins_have_passed_if_so_delete_the_ride,
                trigger="date",run_date=run_time, kwargs={ "ride_id": ride.id },misfire_grace_time=31536000
                )
                 
    

async def add_ride(
    ride_data: RideCreate,
    payment_service: PaymentService = Depends(get_payment_service)
) -> RideOut:
    """Adds an entry of RideCreate to the database and returns an object."""
    
    try:
        from services.rider_service import retrieve_rider_by_rider_id
        rider = await retrieve_rider_by_rider_id(id=ride_data.userId)
        if getattr(rider, "title", None) == "partner":
            ride_data = RideCreate(
                **ride_data.model_dump(),
                rideStatus=RideStatus.findingDriver,
                paymentStatus=False,
            )
    except Exception:
        pass
    
    await check_if_user_has_an_existing_active_ride(user_id=ride_data.userId)
    ride = await create_ride(ride_data)
    if not ride.id:
        raise HTTPException(status_code=500, detail="Ride id missing after creation")
    if ride_data.paymentStatus:
        payment = None
    else:
        payment = await payment_service.create_payment_link(ride_id=ride.id)
        ride = await update_ride(
            {"_id": ObjectId(ride.id)},
            RideUpdate(paymentLink=payment),
        )
    try:
        pickup_location = None
        if ride.origin:
            pickup_location = (ride.origin.latitude, ride.origin.longitude)
        await publish_ride_request(
            ride_id=ride.id,
            pickup=ride.pickup,
            destination=ride.destination,
            vehicle_type=str(ride.vehicleType),
            fare_estimate=ride.price,
            rider_id=ride.userId,
            pickup_location=pickup_location,
        )
    except Exception:
        pass
    
    pending_state_removal_run_time = datetime.now(utc) + timedelta(seconds=240)

    scheduler.add_job(
    check_if_state_is_still_pending_payment_and_delete_ride_if_it_is_still_pending_payment,
    trigger="date",run_date=pending_state_removal_run_time, kwargs={ "ride_id": ride.id },misfire_grace_time=31536000
    )
    scheduler.add_job(
    check_if_state_is_still_finding_driver_and_6_mins_have_passed_if_so_delete_the_ride,
    trigger="date",run_date=pending_state_removal_run_time, kwargs={ "ride_id": ride.id },misfire_grace_time=31536000
    )
    return ride


 
async def add_ride_admin_func(
    ride_data: RideCreate,
    payment_service: PaymentService = Depends(get_payment_service)
) -> RideOut:
    """Adds an entry of RideCreate to the database and returns an object."""
    
 
    
    await check_if_user_has_an_existing_active_ride(user_id=ride_data.userId)
    ride = await create_ride(ride_data)
    if not ride.id:
        raise HTTPException(status_code=500, detail="Ride id missing after creation")
    if ride_data.paymentStatus:
        payment = None
    else:
        payment = await payment_service.create_payment_link(ride_id=ride.id)
        ride = await update_ride(
            {"_id": ObjectId(ride.id)},
            RideUpdate(paymentLink=payment),
        )

    try:
        pickup_location = None
        if ride.origin:
            pickup_location = (ride.origin.latitude, ride.origin.longitude)
        await publish_ride_request(
            ride_id=ride.id,
            pickup=ride.pickup,
            destination=ride.destination,
            vehicle_type=str(ride.vehicleType),
            fare_estimate=ride.price,
            rider_id=ride.userId,
            pickup_location=pickup_location,
        )
    except Exception:
        pass

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

    return True
    
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



async def retrieve_rides_by_user_id(user_id: str) -> List[RideOut]:
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
        return []

    return result


async def retrieve_rides_by_driver_id(driver_id: str) -> List[RideOut]:
    """Retrieves ride object based specific Id 

    Raises:
        HTTPException 404(not found): if  Ride not found in the db
        HTTPException 400(bad request): if  Invalid ride ID format

    Returns:
        _type_: RideOut
    """
    if not ObjectId.is_valid(driver_id):
        raise HTTPException(status_code=400, detail="Invalid ride ID format")

    filter_dict = {"driverId": driver_id}
    result = await get_rides(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Ride not found")

    return result



async def retrieve_rides_by_user_id_and_ride_id(user_id: str,ride_id:str) -> RideOut:
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


async def generate_public_ride_sharing_link_for_rider(ride_id: str, user_id: str) -> RideShareLinkOut:
    ride = await retrieve_rides_by_user_id_and_ride_id(user_id=user_id, ride_id=ride_id)
    if (ride == None) or (ride.id == None):
        raise HTTPException(status_code=500,detail="Ride doesn't exist")
    ride_id = ride.id
    ride_key = f"ride_share:by_ride:{ride_id}"
    share_id = await async_redis.get(ride_key)
    if share_id:
        share_key = f"ride_share:link:{share_id}"
        if not await async_redis.exists(share_key):
            await async_redis.hset(
                share_key,
                mapping={
                    "ride_id": ride_id,
                    "created_by": user_id,
                    "role": "rider",
                    "created_at": str(int(time.time())),
                },
            )
    else:
        share_id = uuid.uuid4().hex
        share_key = f"ride_share:link:{share_id}"
        created_at = str(int(time.time()))
        pipe = async_redis.pipeline()
        pipe.set(ride_key, share_id)
        pipe.hset(
            share_key,
            mapping={
                "ride_id": ride_id,
                "created_by": user_id,
                "role": "rider",
                "created_at": created_at,
            },
        )
        await pipe.execute()

    share_link = f"{FRONTEND_SHARE_RIDE_URL}?share_id={share_id}"
    return RideShareLinkOut(shareId=share_id, shareLink=share_link, rideId=ride_id)


async def retrieve_shared_ride_by_share_id(share_id: str) -> RideOut:
    share_key = f"ride_share:link:{share_id}"
    payload = await async_redis.hgetall(share_key)
    ride_id = payload.get("ride_id")
    if not ride_id:
        raise HTTPException(status_code=404, detail="Share link not found")
    return await retrieve_ride_by_ride_id(id=ride_id)


async def retrieve_rides(start=0,stop=100) -> List[RideOut]:
    """Retrieves RideOut Objects in a list

    Returns:
        _type_: RideOut
    """
    return await get_rides(start=start,stop=stop)


async def update_ride_by_id(
    ride_id: str,
    ride_data: RideUpdate,
    rider_id: str | None = None,
    driver_id: str | None = None,
) -> RideOut:
    """
    Update ride with strict state validation and side-effect handling.
    """

    # 1️⃣ Validate ID
    if not ObjectId.is_valid(ride_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ride ID format",
        )

    # 2️⃣ Fetch ride
    ride = await retrieve_ride_by_ride_id(id=ride_id)
    if not ride:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ride not found",
        )

    # 3️⃣ Build filter
    filter_dict = {"_id": ObjectId(ride_id)}

    if rider_id:
        filter_dict["userId"] = rider_id

    # Driver concurrency guard:
    # - If ride already has a driver and it's not this driver, block.
    # - If ride has no driver yet, allow this driver to claim without filtering by driverId.
    if driver_id:
        if ride.driverId and ride.driverId != driver_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ride already assigned to another driver",
            )
        if ride.driverId:
            filter_dict["driverId"] = driver_id

    # 4️⃣ Prevent no-op updates
    if (
        ride_data.rideStatus is not None
        and ride_data.rideStatus == ride.rideStatus
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ride already in '{ride.rideStatus}' state",
        )

    # 5️⃣ Validate state transition
    if ride_data.rideStatus is not None:
        current_status = ride.rideStatus
        target_status = ride_data.rideStatus

        allowed_next_states = ALLOWED_RIDE_STATUS_TRANSITIONS.get(
            current_status, set()
        )

        if target_status not in allowed_next_states:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid ride status transition: {current_status} → {target_status}",
            )

        # 6️⃣ Apply refund side-effects if applicable
        refund_percentage = RIDE_REFUND_RULES.get(
            (current_status, target_status)
        )

        if refund_percentage is not None:
            try:
                if ride.paymentStatus:
                    payment_service = get_payment_service()
                    if ride.price is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Ride price is missing for refund",
                        )

                    unit_amount = int(ride.price / 10)
                    refund_amount = int(
                        Decimal(unit_amount) * Decimal(str(refund_percentage))
                    )

                    if not ride.checkoutSessionObject or not ride.checkoutSessionObject.payment_intent:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Missing payment intent for refund",
                        )

                    await payment_service.refund(
                        payment_intent_id=ride.checkoutSessionObject.payment_intent,
                        amount=refund_amount,
                    )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=(
                        f"Refund failed during ride transition "
                        f"{current_status} → {target_status}: {e}"
                    ),
                )

    # 7️⃣ Perform update
    result = await update_ride(filter_dict, ride_data)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ride not found or update failed",
        )

    # 8️⃣ Emit SSE status update if status changed
    if ride_data.rideStatus is not None and ride_data.rideStatus != ride.rideStatus:
        try:
            await publish_ride_status_update(
                ride_id=ride_id,
                status=ride_data.rideStatus,
                rider_id=ride.userId,
                driver_id=ride.driverId,
                message=f"Ride status changed to {ride_data.rideStatus.value}",
            )
        except Exception as e:
            print(f"Warning: Failed to emit SSE update for ride {ride_id}: {e}")

    return result




async def update_ride_by_id_admin_func(ride_id: str, ride_data: RideUpdate ) -> RideOut:
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
    
    filter_dict["_id"] = ObjectId(ride_id)
    # CANCEL OF RIDE CASES
    if (ride.rideStatus==RideStatus.findingDriver or ride.rideStatus==RideStatus.pendingPayment) and (ride_data.rideStatus==RideStatus.canceled):
        try:
            if ride.paymentStatus:
                payment_service = get_payment_service()
                if ride.price is None:
                    raise HTTPException(status_code=400, detail="Ride price is missing for refund")
                unit_amount = int(ride.price / 10)
                if not ride.checkoutSessionObject or not ride.checkoutSessionObject.payment_intent:
                    raise HTTPException(status_code=400, detail="Missing payment intent for refund")
                refund_amount = int(Decimal(unit_amount) * Decimal("0.95"))
                await payment_service.refund(
                    payment_intent_id=ride.checkoutSessionObject.payment_intent,
                    amount=refund_amount,
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500,detail=f"Exception occured while processing a refund due to a canceled ride in 'update_ride_by_id_admin_func' {e}")    
        
        
    result = await update_ride(filter_dict, ride_data)
    if not result:
        raise HTTPException(status_code=404, detail="Ride not found or update failed")

    # Emit SSE status update if status changed
    if ride_data.rideStatus is not None and ride_data.rideStatus != ride.rideStatus:
        try:
            await publish_ride_status_update(
                ride_id=ride_id,
                status=ride_data.rideStatus,
                rider_id=ride.userId,
                driver_id=ride.driverId,
                message=f"Ride status changed to {ride_data.rideStatus.value}",
            )
        except Exception as e:
            print(f"Warning: Failed to emit SSE update for ride {ride_id}: {e}")
    
        
    return result



async def update_ride_with_ride_id(ride_id: str, payload: dict ) -> dict:
    """updates an entry of ride in the database

    Raises:
        HTTPException 404(not found): if Ride not found or update failed
        HTTPException 400(not found): Invalid ride ID format

    Returns:
        _type_: RideOut
    """
    if not ObjectId.is_valid(ride_id):
        raise HTTPException(status_code=400, detail="Invalid ride ID format")
    filter_dict={}
    filter_dict["_id"] = ObjectId(ride_id)
    
    # Get current ride to check status change
    current_ride = await retrieve_ride_by_ride_id(id=ride_id)
    
    ride_data = RideUpdate(**payload)

    # Basic status validation similar to update_ride_by_id
    if ride_data.rideStatus is not None:
        if current_ride and ride_data.rideStatus == current_ride.rideStatus:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ride already in '{ride_data.rideStatus}' state",
            )
        if current_ride:
            allowed_next_states = ALLOWED_RIDE_STATUS_TRANSITIONS.get(
                current_ride.rideStatus, set()
            )
            if ride_data.rideStatus not in allowed_next_states:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid ride status transition: {current_ride.rideStatus} → {ride_data.rideStatus}",
                )

    result = await update_ride(filter_dict, ride_data)
    if not result:
        raise HTTPException(status_code=404, detail="Ride not found or update failed")
     
    # Emit SSE status update if status changed
    if ride_data.rideStatus is not None and current_ride and ride_data.rideStatus != current_ride.rideStatus:
        try:            
            await publish_ride_status_update(
                ride_id=ride_id,
                status=ride_data.rideStatus,
                rider_id=current_ride.userId,
                driver_id=current_ride.driverId,
                message=f"Ride status changed to {ride_data.rideStatus.value}",
            )
        except Exception as e:
            print(f"Warning: Failed to emit SSE update for ride {ride_id}: {e}")
    
    return result.model_dump()
