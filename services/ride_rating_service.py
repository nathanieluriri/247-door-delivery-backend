from __future__ import annotations

from typing import Literal, Optional

from core.database import db
from repositories.rating import get_rating
from schemas.imports import RideStatus
from schemas.ride import RideOut, RideRatingStatus


COMPLETED_LIKE_RIDE_STATUSES = {
    RideStatus.completed.value,
    RideStatus.awaitingPayment.value,
    RideStatus.paymentFailed.value,
}


def _ride_status_value(status: RideStatus | str | None) -> str:
    if isinstance(status, RideStatus):
        return status.value
    return str(status or "")


def _is_completed_like_status(status: RideStatus | str | None) -> bool:
    return _ride_status_value(status) in COMPLETED_LIKE_RIDE_STATUSES


async def build_ride_rating_status(ride: RideOut) -> RideRatingStatus:
    ride_id = str(ride.id or "")
    rider_id = str(ride.userId or "")
    driver_id = str(ride.driverId or "")
    completed_like = _is_completed_like_status(ride.rideStatus)

    rider_must_rate = bool(completed_like and ride_id and rider_id and driver_id)
    driver_must_rate = bool(completed_like and ride_id and rider_id and driver_id)

    rider_rated = False
    rider_rated_at: Optional[int] = None
    driver_rated = False
    driver_rated_at: Optional[int] = None

    if rider_must_rate:
        rider_rating = await get_rating(
            {"rideId": ride_id, "raterId": rider_id, "userId": driver_id}
        )
        if rider_rating is not None:
            rider_rated = True
            rider_rated_at = getattr(rider_rating, "date_created", None)

    if driver_must_rate:
        driver_rating = await get_rating(
            {"rideId": ride_id, "raterId": driver_id, "userId": rider_id}
        )
        if driver_rating is not None:
            driver_rated = True
            driver_rated_at = getattr(driver_rating, "date_created", None)

    return RideRatingStatus(
        riderMustRate=rider_must_rate,
        driverMustRate=driver_must_rate,
        riderRated=rider_rated,
        driverRated=driver_rated,
        riderRatedAt=rider_rated_at,
        driverRatedAt=driver_rated_at,
    )


async def find_pending_rating_for_user(
    user_id: str,
    user_type: Literal["rider", "driver"],
) -> Optional[dict[str, str]]:
    role_field = "userId" if user_type == "rider" else "driverId"
    query = {
        role_field: user_id,
        "rideStatus": {"$in": list(COMPLETED_LIKE_RIDE_STATUSES)},
    }
    projection = {
        "_id": 1,
        "userId": 1,
        "driverId": 1,
        "rideStatus": 1,
        "date_created": 1,
        "last_updated": 1,
    }
    cursor = (
        db.rides.find(query, projection=projection)
        .sort([("last_updated", -1), ("date_created", -1)])
        .limit(50)
    )

    async for ride in cursor:
        ride_id = str(ride.get("_id") or "")
        rider_id = str(ride.get("userId") or "")
        driver_id = str(ride.get("driverId") or "")
        if not ride_id or not rider_id or not driver_id:
            continue

        if user_type == "rider":
            existing = await get_rating(
                {"rideId": ride_id, "raterId": user_id, "userId": driver_id}
            )
            if existing is None:
                return {"rideId": ride_id, "code": "RATING_REQUIRED_RIDER"}
        else:
            existing = await get_rating(
                {"rideId": ride_id, "raterId": user_id, "userId": rider_id}
            )
            if existing is None:
                return {"rideId": ride_id, "code": "RATING_REQUIRED_DRIVER"}
    return None
