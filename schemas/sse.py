from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from schemas.imports import RideStatus, UserType
from core.routing_config import DeliveryRouteResponse
from schemas.ride import RideRatingStatus


class SSEEvent(BaseModel):
    id: str
    event: str
    data: Dict[str, Any]
    created_at: int = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}


class SSEEventType(str, Enum):
    ride_request = "ride_request"
    ride_status_update = "ride_status_update"
    chat_message = "chat_message"
    driver_route_update = "driver_route_update"
    profile_action_required = "profile_action_required"


class SSEAck(BaseModel):
    event_id: str = Field(..., alias="eventId")

    model_config = {"populate_by_name": True}


class DriverSnapshot(BaseModel):
    driver_id: str = Field(..., alias="driverId")
    first_name: Optional[str] = Field(default=None, alias="firstName")
    last_name: Optional[str] = Field(default=None, alias="lastName")
    vehicle_type: Optional[str] = Field(default=None, alias="vehicleType")
    vehicle_make: Optional[str] = Field(default=None, alias="vehicleMake")
    vehicle_model: Optional[str] = Field(default=None, alias="vehicleModel")
    vehicle_color: Optional[str] = Field(default=None, alias="vehicleColor")
    vehicle_plate_number: Optional[str] = Field(default=None, alias="vehiclePlateNumber")
    vehicle_year: Optional[int] = Field(default=None, alias="vehicleYear")
    headshot_url: Optional[str] = Field(default=None, alias="headshotUrl")
    rating: Optional[float] = Field(default=None, alias="rating")
    rating_count: Optional[int] = Field(default=None, alias="ratingCount")

    model_config = {"populate_by_name": True}


class RideStatusUpdate(BaseModel):
    ride_id: str = Field(..., alias="rideId")
    status: RideStatus
    message: Optional[str] = None
    eta_minutes: Optional[int] = Field(default=None, alias="etaMinutes")
    action_required: Optional[bool] = Field(default=None, alias="actionRequired")
    action_type: Optional[str] = Field(default=None, alias="actionType")
    decision_options: Optional[list[str]] = Field(default=None, alias="decisionOptions")
    action_deadline_ms: Optional[int] = Field(default=None, alias="actionDeadlineMs")
    reason_code: Optional[str] = Field(default=None, alias="reasonCode")
    driver_snapshot: Optional[DriverSnapshot] = Field(default=None, alias="driverSnapshot")
    rating_status: Optional[RideRatingStatus] = Field(default=None, alias="ratingStatus")

    model_config = {"populate_by_name": True}


class ProfileActionRequiredEvent(BaseModel):
    action_type: str = Field(..., alias="actionType")
    message: str
    field: str
    required: bool = False
    severity: str = "info"
    cta_label: Optional[str] = Field(default=None, alias="ctaLabel")
    cta_path: Optional[str] = Field(default=None, alias="ctaPath")

    model_config = {"populate_by_name": True}


class RideRequestEvent(BaseModel):
    ride_id: str = Field(..., alias="rideId")
    pickup: str
    destination: str
    vehicle_type: str = Field(..., alias="vehicleType")
    fare_estimate: Optional[float] = Field(default=None, alias="fareEstimate")
    rider_id: Optional[str] = Field(default=None, alias="riderId")

    model_config = {"populate_by_name": True}


class DriverRouteUpdate(BaseModel):
    ride_id: str = Field(..., alias="rideId")
    status: RideStatus
    route: Optional[DeliveryRouteResponse] = None
    generated_at: int = Field(..., alias="generatedAt")
    error: Optional[str] = None

    model_config = {"populate_by_name": True}


class ChatMessageEvent(BaseModel):
    chat_id: str = Field(..., alias="chatId")
    ride_id: str = Field(..., alias="rideId")
    sender_id: str = Field(..., alias="senderId")
    sender_type: UserType = Field(..., alias="senderType")
    message: str
    timestamp: int

    model_config = {"populate_by_name": True}
