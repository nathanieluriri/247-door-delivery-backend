from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from schemas.imports import RideStatus, UserType
from core.routing_config import DeliveryRouteResponse


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


class SSEAck(BaseModel):
    event_id: str = Field(..., alias="eventId")

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
