from pydantic import BaseModel
from typing import List, Optional, Dict, Any, TypeVar, Generic
from schemas.place import Location

# Generic type for WebSocket responses
T = TypeVar('T')

class WSResponse(BaseModel, Generic[T]):
    """
    WebSocket Response Schema - Similar to APIResponse but for WebSocket events.

    This provides a consistent structure for all WebSocket responses:
    - status: "success" or "error"
    - message: Human-readable message
    - data: Optional typed data payload
    - event_id: Optional unique identifier for tracking
    """
    status: str  # "success" or "error"
    message: str
    data: Optional[T] = None
    event_id: Optional[str] = None

# Authentication
class AuthenticateRequest(BaseModel):
    token: str

class AuthenticateResponse(BaseModel):
    status: str
    message: str
    user_type: Optional[str] = None
    user_id: Optional[str] = None

# Driver Actions
class GoOnlineRequest(BaseModel):
    pass

class GoOnlineResponse(BaseModel):
    status: str
    message: str
    driver_id: Optional[str] = None

class GoOfflineRequest(BaseModel):
    pass

class GoOfflineResponse(BaseModel):
    status: str
    message: str

class UpdateLocationRequest(BaseModel):
    latitude: float
    longitude: float

class UpdateLocationResponse(BaseModel):
    status: str
    message: str

# Rider Actions
class CancelRideRequest(BaseModel):
    ride_id: str
    reason: Optional[str] = None

class CancelRideResponse(BaseModel):
    status: str
    message: str

# Ride Management (Shared)
class AcceptRideRequest(BaseModel):
    ride_id: str

class AcceptRideResponse(BaseModel):
    status: str
    message: str
    driver_info: Optional[Dict[str, Any]] = None

class StartRideRequest(BaseModel):
    ride_id: str

class StartRideResponse(BaseModel):
    status: str
    message: str

class CompleteRideRequest(BaseModel):
    ride_id: str

class CompleteRideResponse(BaseModel):
    status: str
    message: str
    ride_data: Optional[Dict[str, Any]] = None

class JoinRideRoomRequest(BaseModel):
    ride_id: str

class JoinRideRoomResponse(BaseModel):
    status: str
    message: str
    ride_data: Optional[Dict[str, Any]] = None

class GetRideStateRequest(BaseModel):
    ride_id: str

class GetRideStateResponse(BaseModel):
    status: str
    message: str
    ride_data: Optional[Dict[str, Any]] = None

# Chat
class SendChatRequest(BaseModel):
    ride_id: str
    message: str

class SendChatResponse(BaseModel):
    status: str
    message: str
    chat_id: Optional[str] = None

class GetRideChatsRequest(BaseModel):
    ride_id: str

class GetRideChatsResponse(BaseModel):
    status: str
    message: str
    chats: Optional[List[Dict[str, Any]]] = None

class ChatMessage(BaseModel):
    id: str
    ride_id: str
    sender_id: str
    sender_type: str  # "RIDER" or "DRIVER"
    message: str
    timestamp: int

# Server to Client Events
class RideStatusUpdate(BaseModel):
    status: str  # e.g., "findingDriver", "arrivingToPickup", "drivingToDestination", "completed"
    data: Optional[Dict[str, Any]] = None
    eta_minutes: Optional[int] = None

class NewRideRequest(BaseModel):
    ride_id: str
    pickup: Location
    destination: Location
    vehicle_type: str
    fare_estimate: Optional[float] = None
    rider_info: Optional[Dict[str, Any]] = None

class DriverLocationUpdate(BaseModel):
    driver_id: str
    latitude: float
    longitude: float
    heading: Optional[float] = None

class ServerMessage(BaseModel):
    msg: str

class ErrorResponse(BaseModel):
    message: str
    detail: str
    code: Optional[str] = None