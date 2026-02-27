from __future__ import annotations

from typing import Any, Optional

from bson import ObjectId

from core.storage import get_signed_url
from repositories.driver import get_driver
from repositories.rating import get_user_rating_summary
from schemas.driver_document import DocumentStatus, DocumentType
from services.driver_document_service import get_latest_document_for_driver

DRIVER_RIDE_SNAPSHOT_FIELDS: tuple[str, ...] = (
    "driverFirstName",
    "driverLastName",
    "driverVehicleType",
    "driverVehicleMake",
    "driverVehicleModel",
    "driverVehicleColor",
    "driverVehiclePlateNumber",
    "driverVehicleYear",
    "driverHeadshotFileKey",
    "driverHeadshotUrl",
    "driverHeadshotDocumentId",
    "driverRating",
    "driverRatingCount",
)


def _normalize_vehicle_type(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def resolve_driver_headshot_url(
    file_key: Optional[str],
    fallback_url: Optional[str] = None,
) -> Optional[str]:
    if file_key:
        try:
            signed = get_signed_url(file_key)
            if signed:
                return signed
        except Exception:
            pass
        return fallback_url or file_key
    return fallback_url


async def build_driver_ride_snapshot(driver_id: str) -> dict[str, Any]:
    if not ObjectId.is_valid(driver_id):
        return {}

    driver = await get_driver({"_id": ObjectId(driver_id)})
    if not driver:
        return {}

    headshot_doc = await get_latest_document_for_driver(
        driver_id=driver_id,
        document_type=DocumentType.DRIVER_HEADSHOT,
        statuses=[DocumentStatus.APPROVED],
    )
    headshot_file_key = headshot_doc.fileKey if headshot_doc else None
    headshot_url = resolve_driver_headshot_url(
        file_key=headshot_file_key,
        fallback_url=headshot_doc.signedUrl if headshot_doc else None,
    )
    driver_rating = 0.0
    driver_rating_count = 0
    try:
        rating_summary = await get_user_rating_summary(driver_id)
        driver_rating = float(getattr(rating_summary, "avgRating", 0) or 0)
        driver_rating_count = int(getattr(rating_summary, "totalRides", 0) or 0)
    except Exception:
        pass

    return {
        "driverId": driver.id or driver_id,
        "driverFirstName": driver.firstName,
        "driverLastName": driver.lastName,
        "driverVehicleType": _normalize_vehicle_type(driver.vehicleType),
        "driverVehicleMake": driver.vehicleMake,
        "driverVehicleModel": driver.vehicleModel,
        "driverVehicleColor": driver.vehicleColor,
        "driverVehiclePlateNumber": driver.vehiclePlateNumber,
        "driverVehicleYear": driver.vehicleYear,
        "driverHeadshotFileKey": headshot_file_key,
        "driverHeadshotUrl": headshot_url,
        "driverHeadshotDocumentId": headshot_doc.id if headshot_doc else None,
        "driverRating": driver_rating,
        "driverRatingCount": driver_rating_count,
    }


def ride_snapshot_to_sse_driver_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "driverId": snapshot.get("driverId"),
        "firstName": snapshot.get("driverFirstName"),
        "lastName": snapshot.get("driverLastName"),
        "vehicleType": snapshot.get("driverVehicleType"),
        "vehicleMake": snapshot.get("driverVehicleMake"),
        "vehicleModel": snapshot.get("driverVehicleModel"),
        "vehicleColor": snapshot.get("driverVehicleColor"),
        "vehiclePlateNumber": snapshot.get("driverVehiclePlateNumber"),
        "vehicleYear": snapshot.get("driverVehicleYear"),
        "headshotUrl": snapshot.get("driverHeadshotUrl"),
        "rating": snapshot.get("driverRating"),
        "ratingCount": snapshot.get("driverRatingCount"),
    }


async def build_driver_sse_snapshot(driver_id: str) -> dict[str, Any]:
    snapshot = await build_driver_ride_snapshot(driver_id)
    if not snapshot:
        return {}
    return ride_snapshot_to_sse_driver_snapshot(snapshot)
