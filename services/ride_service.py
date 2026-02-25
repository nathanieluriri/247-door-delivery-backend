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
from typing import Any, List, Optional
from datetime import datetime, timedelta
from datetime import timezone
utc = timezone.utc
from core.payments import PaymentService, get_payment_service
from services.sse_service import publish_ride_status_update, publish_ride_request
from services.payout_service import add_payout
from repositories.payout import get_payouts
from core.redis_cache import async_redis
from core.metrics import match_time_seconds, driver_acceptance_rate, driver_rejects
from repositories.ride import (
    check_if_user_has_an_existing_active_ride,
    create_ride,
    get_ride,
    get_rides,
    update_ride,
    delete_ride,
)
from schemas.imports import ALLOWED_RIDE_STATUS_TRANSITIONS, RIDE_REFUND_RULES, RideStatus, PayoutOptions
from schemas.ride import RideCreate, RideUpdate, RideOut, RideShareLinkOut
from schemas.payout import PayoutCreate
from services.driver_route_service import maybe_publish_driver_route_for_ride


FRONTEND_SHARE_RIDE_URL = os.getenv("FRONTEND_SHARE_RIDE_URL", "http://localhost:8080/share/ride")
SCHEDULED_DISPATCH_LEAD_SECONDS = int(os.getenv("SCHEDULED_DISPATCH_LEAD_SECONDS", "900"))
SCHEDULED_MIN_LEAD_SECONDS = int(os.getenv("SCHEDULED_MIN_LEAD_SECONDS", "300"))
NO_DRIVER_DECISION_WINDOW_SECONDS = int(os.getenv("NO_DRIVER_DECISION_WINDOW_SECONDS", "300"))


def _ride_dispatch_job_id(ride_id: str) -> str:
    return f"ride_dispatch:{ride_id}"


def _ride_activate_job_id(ride_id: str) -> str:
    return f"ride_activate:{ride_id}"


def _ride_no_driver_checkpoint_job_id(ride_id: str) -> str:
    return f"ride_no_driver_checkpoint:{ride_id}"


def _ride_no_driver_decision_timeout_job_id(ride_id: str) -> str:
    return f"ride_no_driver_decision_timeout:{ride_id}"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _datetime_from_epoch_ms(value_ms: int) -> datetime:
    return datetime.fromtimestamp(value_ms / 1000, tz=utc)


def _format_place_for_dispatch(place: Any) -> str:
    if isinstance(place, str):
        return place
    if isinstance(place, dict):
        return (
            place.get("formatted_address")
            or place.get("address")
            or place.get("name")
            or place.get("place_id")
            or "Unknown location"
        )
    return (
        getattr(place, "formatted_address", None)
        or getattr(place, "address", None)
        or getattr(place, "name", None)
        or getattr(place, "place_id", None)
        or "Unknown location"
    )


async def _maybe_create_payout_for_completed_ride(ride: RideOut) -> None:
    if not ride or not ride.driverId or not ride.id:
        return
    if ride.rideStatus != RideStatus.completed:
        return
    if ride.price is None:
        return
    try:
        existing = await get_payouts(
            filter_dict={
                "driverId": ride.driverId,
                "payoutOption": PayoutOptions.totalEarnings,
                "rideIds": ride.id,
            },
            start=0,
            stop=1,
        )
        if existing:
            return
        payout_record = PayoutCreate(
            payoutOption=PayoutOptions.totalEarnings,
            amount=float(ride.price),
            driverId=ride.driverId,
            rideIds=[ride.id],
        )
        await add_payout(payout_record)
    except Exception:
        pass


async def republish_ride_request_until_accepted(ride_id: str) -> None:
    filter_dict = {"_id": ObjectId(ride_id)}
    ride = await get_ride(filter_dict=filter_dict)
    if not ride:
        try:
            scheduler.remove_job(_ride_dispatch_job_id(ride_id))
        except Exception:
            pass
        return

    if ride.rideStatus != RideStatus.matching:
        try:
            scheduler.remove_job(_ride_dispatch_job_id(ride_id))
        except Exception:
            pass
        return

    pickup_location = None
    if ride.origin:
        pickup_location = (ride.origin.latitude, ride.origin.longitude)
    await publish_ride_request(
        ride_id=ride.id, # type: ignore
        pickup=_format_place_for_dispatch(ride.pickup),
        destination=_format_place_for_dispatch(ride.destination),
        vehicle_type=str(ride.vehicleType),
        fare_estimate=ride.price,
        rider_id=ride.userId,
        pickup_location=pickup_location,
    )


def _schedule_dispatch_republish_job(ride_id: str) -> None:
    scheduler.add_job(
        republish_ride_request_until_accepted,
        trigger="interval",
        seconds=10,
        kwargs={"ride_id": ride_id},
        id=_ride_dispatch_job_id(ride_id),
        replace_existing=True,
    )


def _schedule_scheduled_ride_jobs(ride_id: str, dispatch_start_ms: int, pickup_at_ms: int) -> None:
    scheduler.add_job(
        activate_scheduled_ride_for_matching,
        trigger="date",
        run_date=_datetime_from_epoch_ms(dispatch_start_ms),
        kwargs={"ride_id": ride_id},
        id=_ride_activate_job_id(ride_id),
        replace_existing=True,
        misfire_grace_time=31536000,
    )
    scheduler.add_job(
        prompt_no_driver_decision_for_scheduled_ride,
        trigger="date",
        run_date=_datetime_from_epoch_ms(pickup_at_ms),
        kwargs={"ride_id": ride_id},
        id=_ride_no_driver_checkpoint_job_id(ride_id),
        replace_existing=True,
        misfire_grace_time=31536000,
    )


async def activate_scheduled_ride_for_matching(ride_id: str) -> None:
    ride = await get_ride({"_id": ObjectId(ride_id)})
    if not ride or ride.rideStatus != RideStatus.scheduled:
        return

    update_payload = RideUpdate(
        rideStatus=RideStatus.matching,
        noDriverDecision=None,
        noDriverDecisionDeadlineMs=None,
        last_updated=int(time.time()),
    )
    ride = await update_ride({"_id": ObjectId(ride_id)}, update_payload)

    try:
        pickup_location = None
        if ride.origin:
            pickup_location = (ride.origin.latitude, ride.origin.longitude)
        await publish_ride_request(
            ride_id=ride.id,  # type: ignore
            pickup=_format_place_for_dispatch(ride.pickup),
            destination=_format_place_for_dispatch(ride.destination),
            vehicle_type=str(ride.vehicleType),
            fare_estimate=ride.price,
            rider_id=ride.userId,
            pickup_location=pickup_location,
        )
        _schedule_dispatch_republish_job(ride_id)
        await publish_ride_status_update(
            ride_id=ride_id,
            status=RideStatus.matching,
            rider_id=ride.userId,
            driver_id=ride.driverId,
            message="Scheduled ride is now searching for drivers.",
        )
    except Exception:
        pass


async def prompt_no_driver_decision_for_scheduled_ride(ride_id: str) -> None:
    ride = await get_ride({"_id": ObjectId(ride_id)})
    if not ride:
        return
    if ride.rideStatus != RideStatus.matching or ride.driverId:
        return

    now_ms = _now_ms()
    deadline_ms = now_ms + (NO_DRIVER_DECISION_WINDOW_SECONDS * 1000)
    await update_ride(
        {"_id": ObjectId(ride_id)},
        RideUpdate(
            noDriverPromptedAtMs=now_ms,
            noDriverDecision=None,
            noDriverDecisionDeadlineMs=deadline_ms,
            last_updated=int(time.time()),
        ),
    )
    scheduler.add_job(
        resolve_no_driver_decision_timeout,
        trigger="date",
        run_date=_datetime_from_epoch_ms(deadline_ms),
        kwargs={"ride_id": ride_id},
        id=_ride_no_driver_decision_timeout_job_id(ride_id),
        replace_existing=True,
        misfire_grace_time=31536000,
    )
    try:
        await publish_ride_status_update(
            ride_id=ride_id,
            status=RideStatus.matching,
            rider_id=ride.userId,
            driver_id=ride.driverId,
            message=(
                "No driver available at pickup time. "
                "Choose Keep Searching or Cancel Ride in the app."
            ),
            action_required=True,
            action_type="no_driver_decision",
            decision_options=["keep_searching", "cancel_ride"],
            action_deadline_ms=deadline_ms,
            reason_code="no_driver_at_pickup",
        )
    except Exception:
        pass


async def resolve_no_driver_decision_timeout(ride_id: str) -> None:
    ride = await get_ride({"_id": ObjectId(ride_id)})
    if not ride:
        return
    if ride.rideStatus != RideStatus.matching:
        return
    if ride.noDriverDecision:
        return

    await update_ride(
        {"_id": ObjectId(ride_id)},
        RideUpdate(
            noDriverDecision="keep_searching",
            noDriverDecisionDeadlineMs=None,
            last_updated=int(time.time()),
        ),
    )

def _prepare_scheduling_fields(ride_data: RideCreate) -> RideCreate:
    now_ms = _now_ms()
    pickup_schedule_ms = int(ride_data.pickupSchedule or 0)
    is_scheduled = pickup_schedule_ms > 0

    if is_scheduled:
        if pickup_schedule_ms <= now_ms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="pickupSchedule must be a future Unix epoch timestamp in milliseconds",
            )
        if pickup_schedule_ms - now_ms < (SCHEDULED_MIN_LEAD_SECONDS * 1000):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Scheduled rides must be at least {SCHEDULED_MIN_LEAD_SECONDS} seconds in the future",
            )

    dispatch_start_ms = (
        max(now_ms, pickup_schedule_ms - (SCHEDULED_DISPATCH_LEAD_SECONDS * 1000))
        if is_scheduled
        else None
    )
    target_status = RideStatus.scheduled if is_scheduled else RideStatus.matching

    return RideCreate(
        **ride_data.model_dump(),
        paymentStatus=False,
        rideStatus=target_status,
        isScheduled=is_scheduled,
        scheduledPickupAtMs=pickup_schedule_ms if is_scheduled else None,
        dispatchStartAtMs=dispatch_start_ms,
        noDriverPromptedAtMs=None,
        noDriverDecision=None,
        noDriverDecisionDeadlineMs=None,
        paymentDueAtMs=None,
        paymentAttempts=0,
        cancelReason=None,
    )


async def _dispatch_or_schedule_ride(ride: RideOut) -> None:
    if not ride.id:
        return

    if ride.rideStatus == RideStatus.scheduled:
        if not ride.scheduledPickupAtMs or not ride.dispatchStartAtMs:
            return
        _schedule_scheduled_ride_jobs(
            ride_id=ride.id,
            dispatch_start_ms=ride.dispatchStartAtMs,
            pickup_at_ms=ride.scheduledPickupAtMs,
        )
        return

    if ride.rideStatus != RideStatus.matching:
        return

    pickup_location = None
    if ride.origin:
        pickup_location = (ride.origin.latitude, ride.origin.longitude)
    await publish_ride_request(
        ride_id=ride.id,  # type: ignore
        pickup=_format_place_for_dispatch(ride.pickup),
        destination=_format_place_for_dispatch(ride.destination),
        vehicle_type=str(ride.vehicleType),
        fare_estimate=ride.price,
        rider_id=ride.userId,
        pickup_location=pickup_location,
    )
    _schedule_dispatch_republish_job(ride.id)


async def add_ride(
    ride_data: RideCreate,
    payment_service: PaymentService = Depends(get_payment_service)
) -> RideOut:
    """Adds an entry of RideCreate to the database and returns an object."""

    _ = payment_service
    try:
        from services.rider_service import retrieve_rider_by_rider_id

        rider = await retrieve_rider_by_rider_id(id=ride_data.userId)
        if getattr(rider, "title", None) == "partner":
            ride_data = RideCreate(
                **ride_data.model_dump(),
                rideStatus=RideStatus.matching,
                paymentStatus=False,
            )
    except Exception:
        pass

    ride_data = _prepare_scheduling_fields(ride_data)
    await check_if_user_has_an_existing_active_ride(user_id=ride_data.userId)
    ride = await create_ride(ride_data)
    if not ride.id:
        raise HTTPException(status_code=500, detail="Ride id missing after creation")

    try:
        await _dispatch_or_schedule_ride(ride)
    except Exception:
        pass
    return ride


async def add_ride_admin_func(
    ride_data: RideCreate,
    payment_service: PaymentService = Depends(get_payment_service)
) -> RideOut:
    """Adds an entry of RideCreate to the database and returns an object."""

    _ = payment_service
    ride_data = _prepare_scheduling_fields(ride_data)
    await check_if_user_has_an_existing_active_ride(user_id=ride_data.userId)
    ride = await create_ride(ride_data)
    if not ride.id:
        raise HTTPException(status_code=500, detail="Ride id missing after creation")

    try:
        await _dispatch_or_schedule_ride(ride)
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
        HTTPException 400(bad request): if  Invalid driver ID format

    Returns:
        _type_: RideOut
    """
    if not ObjectId.is_valid(driver_id):
        print("driver_id",driver_id)
        
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    filter_dict = {"driverId": driver_id}
    result = await get_rides(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Ride not found")

    return result


async def retrieve_active_ride_for_driver(driver_id: str) -> Optional[RideOut]:
    if not ObjectId.is_valid(driver_id):
        raise HTTPException(status_code=400, detail="Invalid driver ID format")
    filter_dict = {
        "driverId": driver_id,
        "rideStatus": {"$in": [RideStatus.arrivingToPickup, RideStatus.drivingToDestination]},
    }
    result = await get_rides(filter_dict, start=0, stop=1)
    if not result:
        return None
    return result[0]


async def retrieve_rides_by_user_id_and_ride_id(user_id: str,ride_id:str) -> RideOut:
    """Retrieves ride object based specific Id 

    Raises:
        HTTPException 404(not found): if  Ride not found in the db
        HTTPException 400(bad request): if  Invalid ride ID format

    Returns:
        _type_: RideOut
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

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


async def decide_no_driver_for_ride(ride_id: str, rider_id: str, decision: str) -> RideOut:
    ride = await retrieve_rides_by_user_id_and_ride_id(user_id=rider_id, ride_id=ride_id)
    if ride.rideStatus != RideStatus.matching:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ride is not currently in matching state",
        )
    if ride.noDriverDecisionDeadlineMs is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No pending no-driver decision exists for this ride",
        )

    normalized = decision.strip().lower()
    if normalized not in {"keep_searching", "cancel_ride"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="decision must be either 'keep_searching' or 'cancel_ride'",
        )

    if normalized == "cancel_ride":
        return await update_ride_by_id(
            ride_id=ride_id,
            rider_id=rider_id,
            ride_data=RideUpdate(
                rideStatus=RideStatus.canceled,
                noDriverDecision=normalized,
                noDriverDecisionDeadlineMs=None,
                cancelReason="user_canceled_after_no_driver_prompt",
            ),
        )

    return await update_ride_by_id(
        ride_id=ride_id,
        rider_id=rider_id,
        ride_data=RideUpdate(
            noDriverDecision=normalized,
            noDriverDecisionDeadlineMs=None,
        ),
    )


async def rehydrate_scheduled_ride_jobs() -> None:
    now_ms = _now_ms()
    open_rides = await get_rides(
        filter_dict={
            "rideStatus": {
                "$in": [
                    RideStatus.scheduled.value,
                    RideStatus.matching.value,
                    RideStatus.findingDriver.value,
                ]
            },
        },
        start=0,
        stop=1000,
    )
    for ride in open_rides:
        if not ride.id:
            continue
        try:
            if ride.rideStatus == RideStatus.scheduled:
                if not ride.scheduledPickupAtMs:
                    continue
                dispatch_start_ms = ride.dispatchStartAtMs or max(
                    now_ms,
                    ride.scheduledPickupAtMs - (SCHEDULED_DISPATCH_LEAD_SECONDS * 1000),
                )
                _schedule_scheduled_ride_jobs(
                    ride_id=ride.id,
                    dispatch_start_ms=dispatch_start_ms,
                    pickup_at_ms=ride.scheduledPickupAtMs,
                )
            elif ride.rideStatus == RideStatus.matching:
                _schedule_dispatch_republish_job(ride.id)
                if (
                    ride.noDriverDecisionDeadlineMs
                    and ride.noDriverDecision is None
                    and ride.noDriverDecisionDeadlineMs > now_ms
                ):
                    scheduler.add_job(
                        resolve_no_driver_decision_timeout,
                        trigger="date",
                        run_date=_datetime_from_epoch_ms(ride.noDriverDecisionDeadlineMs),
                        kwargs={"ride_id": ride.id},
                        id=_ride_no_driver_decision_timeout_job_id(ride.id),
                        replace_existing=True,
                        misfire_grace_time=31536000,
                    )
            elif ride.rideStatus == RideStatus.findingDriver:
                await update_ride(
                    {"_id": ObjectId(ride.id)},
                    RideUpdate(rideStatus=RideStatus.matching, last_updated=int(time.time())),
                )
                _schedule_dispatch_republish_job(ride.id)
        except Exception:
            continue


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
        filter_dict["userId"] = rider_id # type: ignore

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
            filter_dict["driverId"] = driver_id # type: ignore

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
            current_status, set() # type: ignore
        ) # type: ignore

        if target_status not in allowed_next_states:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid ride status transition: {current_status} → {target_status}",
            )

        # 6️⃣ Apply refund side-effects if applicable
        refund_percentage = RIDE_REFUND_RULES.get(
            (current_status, target_status) # type: ignore
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

    if ride_data.rideStatus == RideStatus.awaitingPayment:
        try:
            payment_service = get_payment_service()
            payment_link = await payment_service.create_payment_link(ride_id=ride_id)
            ride_data = ride_data.model_copy(
                update={
                    "paymentLink": payment_link,
                    "paymentDueAtMs": _now_ms(),
                    "paymentAttempts": (ride.paymentAttempts or 0) + 1,
                    "last_updated": int(time.time()),
                }
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to create postpaid payment link: {err}",
            ) from err

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

        # Record acceptance timing when a driver takes the ride
        if (
            ride.rideStatus in {RideStatus.findingDriver, RideStatus.matching}
            and ride_data.rideStatus == RideStatus.arrivingToPickup
        ):
            try:
                started = ride.date_created or ride.last_updated
                if started:
                    duration = time.time() - started
                    match_time_seconds.observe(max(duration, 0))
                driver_acceptance_rate.inc()
            except Exception:
                pass

        if ride_data.rideStatus in {RideStatus.arrivingToPickup, RideStatus.drivingToDestination}:
            try:
                await maybe_publish_driver_route_for_ride(
                    result,
                    status=ride_data.rideStatus,
                    force=True,
                )
            except Exception:
                pass

        if ride_data.rideStatus == RideStatus.completed:
            try:
                await _maybe_create_payout_for_completed_ride(result)
            except Exception:
                pass

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
    if (
        ride.rideStatus in {
            RideStatus.scheduled,
            RideStatus.matching,
            RideStatus.findingDriver,
            RideStatus.pendingPayment,
            RideStatus.arrivingToPickup,
        }
    ) and (ride_data.rideStatus==RideStatus.canceled):
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
        
    if ride_data.rideStatus == RideStatus.awaitingPayment:
        try:
            payment_service = get_payment_service()
            payment_link = await payment_service.create_payment_link(ride_id=ride_id)
            ride_data = ride_data.model_copy(
                update={
                    "paymentLink": payment_link,
                    "paymentDueAtMs": _now_ms(),
                    "paymentAttempts": (ride.paymentAttempts or 0) + 1,
                    "last_updated": int(time.time()),
                }
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to create postpaid payment link: {err}",
            ) from err
        
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

        if ride_data.rideStatus in {RideStatus.arrivingToPickup, RideStatus.drivingToDestination}:
            try:
                await maybe_publish_driver_route_for_ride(
                    result,
                    status=ride_data.rideStatus,
                    force=True,
                )
            except Exception:
                pass

        if ride_data.rideStatus == RideStatus.completed:
            try:
                await _maybe_create_payout_for_completed_ride(result)
            except Exception:
                pass
    
        
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
                current_ride.rideStatus, set() # type: ignore
            ) # type: ignore
            if ride_data.rideStatus not in allowed_next_states:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid ride status transition: {current_ride.rideStatus} → {ride_data.rideStatus}",
                )

    if ride_data.rideStatus == RideStatus.awaitingPayment:
        try:
            payment_service = get_payment_service()
            payment_link = await payment_service.create_payment_link(ride_id=ride_id)
            payment_attempts = (current_ride.paymentAttempts or 0) + 1 if current_ride else 1
            ride_data = ride_data.model_copy(
                update={
                    "paymentLink": payment_link,
                    "paymentDueAtMs": _now_ms(),
                    "paymentAttempts": payment_attempts,
                    "last_updated": int(time.time()),
                }
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to create postpaid payment link: {err}",
            ) from err

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

        if ride_data.rideStatus in {RideStatus.arrivingToPickup, RideStatus.drivingToDestination}:
            try:
                await maybe_publish_driver_route_for_ride(
                    result,
                    status=ride_data.rideStatus,
                    force=True,
                )
            except Exception:
                pass

        if ride_data.rideStatus == RideStatus.completed:
            try:
                await _maybe_create_payout_for_completed_ride(result)
            except Exception:
                pass
    
    return result.model_dump()
