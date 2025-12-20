from pydantic import BaseModel
from typing import Optional, Dict, Any
from schemas.place import Location

# Authentication
class AuthenticateRequest(BaseModel):
    token: str

class AuthenticateResponse(BaseModel):
    status: str  # "success" or "error"
    message: str
    user_type: Optional[str] = None
    user_id: Optional[str] = None

# Driver Actions
class GoOnlineRequest(BaseModel):
    pass  # No data needed

class GoOnlineResponse(BaseModel):
    status: str
    message: str

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

# Ride Requests
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

# Rider Actions
class RequestRideRequest(BaseModel):
    pickup: Location
    dropoff: Location
    vehicle_type: str

class RequestRideResponse(BaseModel):
    status: str
    message: str
    ride_id: Optional[str] = None

class CancelRideRequest(BaseModel):
    ride_id: str

class CancelRideResponse(BaseModel):
    status: str
    message: str

# Rider Actions
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

# Server to Client Events
class RideStatusUpdate(BaseModel):
    status: str  # e.g., "ACCEPTED", "STARTED", "COMPLETED"
    data: Optional[Dict[str, Any]] = None
    eta_minutes: Optional[int] = None

class NewRideRequest(BaseModel):
    ride_id: str
    pickup: Location
    dropoff: Location
    vehicle_type: str
    fare_estimate: Optional[float] = None

class ServerMessage(BaseModel):
    msg: str
    
    
class ErrorResponse(BaseModel):
    message:str
    detail:str