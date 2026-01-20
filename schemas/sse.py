from pydantic import BaseModel, Field
from typing import Any, Dict, Optional

from schemas.imports import RideStatus, UserType


class SSEEvent(BaseModel):
    id: str
    event: str
    data: Dict[str, Any]
    created_at: int = Field(..., alias="createdAt")

    model_config = {"populate_by_name": True}


class SSEAck(BaseModel):
    event_id: str = Field(..., alias="eventId")

    model_config = {"populate_by_name": True}


class RideStatusUpdate(BaseModel):
    ride_id: str = Field(..., alias="rideId")
    status: RideStatus
    message: Optional[str] = None
    eta_minutes: Optional[int] = Field(default=None, alias="etaMinutes")

    model_config = {"populate_by_name": True}


class RideRequestEvent(BaseModel):
    ride_id: str = Field(..., alias="rideId")
    pickup: str
    destination: str
    vehicle_type: str = Field(..., alias="vehicleType")
    fare_estimate: Optional[float] = Field(default=None, alias="fareEstimate")
    rider_id: Optional[str] = Field(default=None, alias="riderId")

    model_config = {"populate_by_name": True}


class ChatMessageEvent(BaseModel):
    chat_id: str = Field(..., alias="chatId")
    ride_id: str = Field(..., alias="rideId")
    sender_id: str = Field(..., alias="senderId")
    sender_type: UserType = Field(..., alias="senderType")
    message: str
    timestamp: int

    model_config = {"populate_by_name": True}
