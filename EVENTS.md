# WebSocket Events Documentation

## Overview

This document outlines the WebSocket event system for the ride-sharing application. WebSockets are used for **real-time status updates, chat, and location sharing** - NOT for ride creation, payments, or ratings.

### Architecture Principles

1. **REST for Actions**: Ride requests, payments, ratings, and profile management use REST APIs
2. **WebSocket for Real-time**: Status updates, chat, and live location sharing
3. **Room-based Communication**: Users only receive events for their active rides
4. **Authentication Required**: All WebSocket connections require JWT authentication

## Event Categories

### 🔐 Authentication Events

#### `authenticate`
**Direction**: Client → Server
**Purpose**: Authenticate WebSocket connection with JWT
**Payload**:
```json
{
  "token": "jwt_token_here"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Authenticated successfully",
  "user_type": "RIDER|DRIVER",
  "user_id": "user_id"
}
```

### 👨‍💼 Driver Events

#### `go_online`
**Direction**: Client → Server
**Purpose**: Mark driver as available for rides
**Payload**: `{}`
**Response**:
```json
{
  "status": "success",
  "message": "Driver is now online",
  "driver_id": "driver_id"
}
```

#### `go_offline`
**Direction**: Client → Server
**Purpose**: Mark driver as unavailable
**Payload**: `{}`
**Response**:
```json
{
  "status": "success",
  "message": "Driver is now offline"
}
```

#### `update_location`
**Direction**: Client → Server
**Purpose**: Update driver's real-time location
**Payload**:
```json
{
  "latitude": 37.7749,
  "longitude": -122.4194
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Location updated"
}
```

#### `accept_ride`
**Direction**: Client → Server
**Purpose**: Driver accepts a ride request
**Payload**:
```json
{
  "ride_id": "ride_123"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Ride accepted",
  "driver_info": {
    "name": "John Doe",
    "rating": 4.8,
    "vehicle": "Toyota Camry"
  }
}
```

#### `start_ride`
**Direction**: Client → Server
**Purpose**: Driver starts the trip
**Payload**:
```json
{
  "ride_id": "ride_123"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Ride started"
}
```

#### `complete_ride`
**Direction**: Client → Server
**Purpose**: Driver completes the trip
**Payload**:
```json
{
  "ride_id": "ride_123"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Ride completed",
  "ride_data": {
    "fare": 25.50,
    "distance": 12.3,
    "duration": 1800
  }
}
```

#### `cancel_ride`
**Direction**: Client → Server
**Purpose**: Driver cancels an accepted ride
**Payload**:
```json
{
  "ride_id": "ride_123",
  "reason": "Traffic accident"
}
```

### 👤 Rider Events

#### `join_ride_room`
**Direction**: Client → Server
**Purpose**: Join WebSocket room after creating ride via REST API
**Payload**:
```json
{
  "ride_id": "ride_123"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Joined ride room",
  "ride_data": {
    "status": "findingDriver",
    "pickup": "123 Main St",
    "destination": "456 Oak Ave"
  }
}
```

#### `get_ride_state`
**Direction**: Client → Server
**Purpose**: Get current ride state (useful for reconnection)
**Payload**:
```json
{
  "ride_id": "ride_123"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Ride state retrieved",
  "ride_data": {
    "status": "arrivingToPickup",
    "driver": {
      "name": "John Doe",
      "rating": 4.8,
      "eta": 5
    }
  }
}
```

#### `cancel_ride`
**Direction**: Client → Server
**Purpose**: Rider cancels ride request or active ride
**Payload**:
```json
{
  "ride_id": "ride_123",
  "reason": "Changed my mind"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Ride canceled"
}
```

**Note**: Driver rating is handled via REST API (`POST /api/v1/riders/rate/driver`)

### 💬 Chat Events

#### `send_chat_message`
**Direction**: Client → Server
**Purpose**: Send chat message in ride conversation
**Payload**:
```json
{
  "ride_id": "ride_123",
  "message": "I'm here!"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Message sent",
  "chat_id": "chat_456"
}
```

#### `get_ride_chats`
**Direction**: Client → Server
**Purpose**: Get all chat messages for a specific ride
**Payload**:
```json
{
  "ride_id": "ride_123"
}
```
**Response**:
```json
{
  "status": "success",
  "message": "Retrieved 5 chat messages",
  "chats": [
    {
      "id": "chat_456",
      "rideId": "ride_123",
      "userId": "user_789",
      "userType": "DRIVER",
      "message": "I'm at the pickup location",
      "timestamp": 1640995200
    }
  ]
}
```

## 📡 Server-to-Client Events

### Ride Status Updates

#### `ride_status_update`
**Direction**: Server → Client
**Purpose**: Broadcast ride status changes to all participants
**Payload**:
```json
{
  "status": "arrivingToPickup",
  "data": {
    "driver": {
      "name": "John Doe",
      "rating": 4.8,
      "vehicle": "Toyota Camry"
    },
    "message": "Driver John is on the way!"
  },
  "eta_minutes": 10
}
```

#### `driver_location_update`
**Direction**: Server → Client
**Purpose**: Share driver's real-time location during trip
**Payload**:
```json
{
  "driver_id": "driver_123",
  "latitude": 37.7749,
  "longitude": -122.4194,
  "heading": 45.0
}
```

#### `chat_message`
**Direction**: Server → Client
**Purpose**: Deliver chat messages to ride participants
**Payload**:
```json
{
  "id": "chat_456",
  "ride_id": "ride_123",
  "sender_id": "user_789",
  "sender_type": "DRIVER",
  "message": "I'm at the pickup location",
  "timestamp": 1640995200
}
```

#### `new_ride_request`
**Direction**: Server → Client (Drivers only)
**Purpose**: Notify nearby drivers of new ride requests
**Payload**:
```json
{
  "ride_id": "ride_123",
  "pickup": {
    "latitude": 37.7749,
    "longitude": -122.4194
  },
  "destination": {
    "latitude": 37.7849,
    "longitude": -122.4094
  },
  "vehicle_type": "standard",
  "fare_estimate": 25.50,
  "rider_info": {
    "rating": 4.7
  }
}
```

## 🔄 Complete Ride Flow

### For Riders:
1. **REST**: `POST /api/v1/riders/rides` - Create ride request
2. **WebSocket**: `join_ride_room` - Join real-time updates
3. **WebSocket**: `get_ride_chats` - Load chat history (optional)
4. **WebSocket**: Receive `ride_status_update` events
5. **WebSocket**: Receive `driver_location_update` during trip
6. **WebSocket**: Use `send_chat_message` for communication
7. **REST**: `POST /api/v1/riders/rate/driver` - Rate driver after completion

### For Drivers:
1. **WebSocket**: `go_online` - Become available
2. **WebSocket**: Receive `new_ride_request` notifications
3. **WebSocket**: `accept_ride` - Accept ride request
4. **WebSocket**: `start_ride` - Begin trip
5. **WebSocket**: `get_ride_chats` - Load chat history (optional)
6. **WebSocket**: `update_location` - Share location during trip
7. **WebSocket**: `complete_ride` - Finish trip

## 🛡️ Security & Best Practices

### Authentication
- All WebSocket connections require JWT authentication
- User type (RIDER/DRIVER) determines available events
- Room-based isolation prevents eavesdropping

### Rate Limiting
- Location updates: Max 1 per second
- Chat messages: Max 5 per minute
- Status updates: No rate limiting (system controlled)

### Error Handling
- All responses include `status` ("success" or "error")
- Error responses include `message` and optional `detail`
- Clients should handle disconnection/reconnection gracefully

### Performance
- Redis pub/sub for scalable broadcasting
- Room-based message filtering
- Efficient JSON serialization with Pydantic

## 📝 Implementation Notes

- **Ride Creation**: Always use REST API (`POST /api/v1/riders/rides`)
- **Driver Rating**: Always use REST API (`POST /api/v1/riders/rate/driver`)
- **Payments**: Always use REST API (`POST /api/v1/riders/payment`)
- **WebSocket Purpose**: Real-time updates, chat, and location sharing only
- **State Management**: WebSocket events update ride status in database
- **Offline Handling**: Clients should reconnect and call `get_ride_state`
- **Testing**: Use tools like WebSocket King or Postman for testing
```json
{
  "status": "success|error",
  "message": "Driver status message",
  "driver_id": "driver_id_string"
}
```

### `go_offline`
**Direction**: Client → Server
**Purpose**: Mark driver as unavailable
**Requirements**: Driver must be authenticated

**Request Schema**:
```json
{}
```

**Response Event**: `go_offline_response`
```json
{
  "status": "success|error",
  "message": "Driver status message"
}
```

### `update_location`
**Direction**: Client → Server
**Purpose**: Update driver's real-time location
**Requirements**: Driver must be online

**Request Schema**:
```json
{
  "latitude": 37.7749,
  "longitude": -122.4194
}
```

**Response Event**: `update_location_response`
```json
{
  "status": "success|error",
  "message": "Location update result"
}
```

## Rider Events

### `request_ride`
**Direction**: Client → Server
**Purpose**: Request a new ride
**Requirements**: Rider must be authenticated

**Request Schema**:
```json
{
  "pickup": {
    "latitude": 37.7749,
    "longitude": -122.4194
  },
  "destination": {
    "latitude": 37.7849,
    "longitude": -122.4094
  },
  "vehicle_type": "standard|premium|xl",
  "notes": "Optional rider notes"
}
```

**Response Event**: `request_ride_response`
```json
{
  "status": "success|error",
  "message": "Ride request result",
  "ride_id": "ride_id_string",
  "estimated_fare": 25.50,
  "estimated_duration": 15
}
```

### `cancel_ride`
**Direction**: Client → Server
**Purpose**: Cancel a ride request or active ride
**Requirements**: Rider must be authenticated and have an active ride

**Request Schema**:
```json
{
  "ride_id": "ride_id_string",
  "reason": "Optional cancellation reason"
}
```

**Response Event**: `cancel_ride_response`
```json
{
  "status": "success|error",
  "message": "Cancellation result"
}
```

### `rate_driver`
**Direction**: Client → Server
**Purpose**: Rate driver after ride completion
**Requirements**: Rider must be authenticated, ride must be completed

**Request Schema**:
```json
{
  "ride_id": "ride_id_string",
  "rating": 5,
  "comment": "Optional review comment"
}
```

**Response Event**: `rate_driver_response`
```json
{
  "status": "success|error",
  "message": "Rating submission result"
}
```

### `join_ride_room`
**Direction**: Client → Server
**Purpose**: Join WebSocket room for ride updates after HTTP ride creation
**Requirements**: Rider must be authenticated

**Request Schema**:
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event**: `join_ride_room_response`
```json
{
  "status": "success|error",
  "message": "Room join result",
  "ride_data": {
    "id": "ride_id",
    "status": "findingDriver",
    "pickup": "pickup_address",
    "destination": "destination_address"
  }
}
```

### `get_ride_state`
**Direction**: Client → Server
**Purpose**: Get current ride state (useful for reconnection)
**Requirements**: Rider must be authenticated

**Request Schema**:
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event**: `get_ride_state_response`
```json
{
  "status": "success|error",
  "message": "State retrieval result",
  "ride_data": {
    "id": "ride_id",
    "status": "arrivingToPickup",
    "driver_info": {...},
    "eta_minutes": 5
  }
}
```

## Ride Management Events

### `accept_ride`
**Direction**: Client → Server
**Purpose**: Driver accepts a ride request
**Requirements**: Driver must be online and authenticated

**Request Schema**:
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event**: `accept_ride_response`
```json
{
  "status": "success|error",
  "message": "Ride acceptance result",
  "driver_info": {
    "id": "driver_id",
    "name": "Driver Name",
    "vehicle": "Vehicle Info",
    "rating": 4.8
  }
}
```

### `start_ride`
**Direction**: Client → Server
**Purpose**: Driver starts the trip
**Requirements**: Driver must have accepted ride and be at pickup location

**Request Schema**:
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event**: `start_ride_response`
```json
{
  "status": "success|error",
  "message": "Ride start result"
}
```

### `complete_ride`
**Direction**: Client → Server
**Purpose**: Driver completes the trip
**Requirements**: Ride must be in progress

**Request Schema**:
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event**: `complete_ride_response`
```json
{
  "status": "success|error",
  "message": "Ride completion result",
  "ride_data": {
    "id": "ride_id",
    "fare": 25.50,
    "distance": 5.2,
    "duration": 18
  }
}
```

## Chat Events

### `send_chat_message`
**Direction**: Client → Server
**Purpose**: Send a chat message in ride conversation
**Requirements**: User must be authenticated and part of the ride

**Request Schema**:
```json
{
  "ride_id": "ride_id_string",
  "message": "Hello, I'm running 5 minutes late!"
}
```

**Response Event**: `send_chat_message_response`
```json
{
  "status": "success|error",
  "message": "Message send result",
  "chat_id": "message_id_string"
}
```

## Server-to-Client Events

These events are emitted by the server to notify clients of updates.

### `server_message`
**Direction**: Server → Client
**Purpose**: General server notifications
**Trigger**: Connection, system announcements

```json
{
  "msg": "Welcome to the ride-sharing service!"
}
```

### `ride_status_update`
**Direction**: Server → Client
**Purpose**: Notify all ride participants of status changes
**Trigger**: Ride status transitions

```json
{
  "status": "arrivingToPickup|drivingToDestination|completed|canceled",
  "data": {
    "message": "Driver is arriving in 5 minutes",
    "driver_info": {...},
    "eta_minutes": 5
  },
  "eta_minutes": 5
}
```

### `chat_message`
**Direction**: Server → Client
**Purpose**: Broadcast chat messages to ride participants
**Trigger**: When a chat message is sent

```json
{
  "id": "message_id",
  "ride_id": "ride_id_string",
  "sender_id": "user_id",
  "sender_type": "RIDER|DRIVER",
  "message": "On my way!",
  "timestamp": 1703123456
}
```

### `driver_location_update`
**Direction**: Server → Client
**Purpose**: Send real-time driver location to rider
**Trigger**: Periodic location updates during ride

```json
{
  "driver_id": "driver_id_string",
  "latitude": 37.7749,
  "longitude": -122.4194,
  "heading": 90.5
}
```

### `new_ride_request`
**Direction**: Server → Client
**Purpose**: Notify drivers of new ride requests
**Trigger**: When rider requests a ride

```json
{
  "ride_id": "ride_id_string",
  "pickup": {
    "latitude": 37.7749,
    "longitude": -122.4194
  },
  "destination": {
    "latitude": 37.7849,
    "longitude": -122.4094
  },
  "vehicle_type": "standard",
  "fare_estimate": 25.50,
  "rider_info": {
    "name": "John Doe",
    "rating": 4.9
  }
}
```

## Response Schema

All WebSocket responses follow a consistent schema pattern similar to REST API responses:

```python
class WSResponse(BaseModel, Generic[T]):
    status: str  # "success" or "error"
    message: str
    data: Optional[T] = None
    event_id: Optional[str] = None
```

### Error Responses
```json
{
  "message": "Error description",
  "detail": "Detailed error information",
  "code": "ERROR_CODE"
}
```

## Event Flow Examples

### Complete Ride Flow (Rider Perspective)

1. **Connect & Authenticate**
   - `authenticate` → `authenticate_response`

2. **Request Ride**
   - `request_ride` → `request_ride_response`
   - Server: `new_ride_request` (to nearby drivers)

3. **Join Ride Room**
   - `join_ride_room` → `join_ride_room_response`

4. **Receive Updates**
   - Server: `ride_status_update` (findingDriver → arrivingToPickup)
   - Server: `driver_location_update` (periodic)
   - Server: `chat_message` (if driver messages)

5. **Chat with Driver**
   - `send_chat_message` → `send_chat_message_response`
   - Server: `chat_message` (broadcast to room)

6. **Ride Progress**
   - Server: `ride_status_update` (arrivingToPickup → drivingToDestination)
   - Server: `ride_status_update` (drivingToDestination → completed)

7. **Rate Driver**
   - `rate_driver` → `rate_driver_response`

### Complete Ride Flow (Driver Perspective)

1. **Connect & Authenticate**
   - `authenticate` → `authenticate_response`

2. **Go Online**
   - `go_online` → `go_online_response`

3. **Update Location**
   - `update_location` → `update_location_response` (periodic)

4. **Receive Ride Requests**
   - Server: `new_ride_request`

5. **Accept Ride**
   - `accept_ride` → `accept_ride_response`
   - Server: `ride_status_update` (broadcast to rider)

6. **Chat with Rider**
   - `send_chat_message` → `send_chat_message_response`
   - Server: `chat_message` (broadcast to room)

7. **Update Location** (during transit)
   - `update_location` → `update_location_response` (frequent)

8. **Start Ride**
   - `start_ride` → `start_ride_response`
   - Server: `ride_status_update`

9. **Complete Ride**
   - `complete_ride` → `complete_ride_response`
   - Server: `ride_status_update`

## Notes

### Chatting
- Chat messages are broadcast to all participants in the ride room
- Messages are persisted to database for history
- Real-time delivery with fallback to polling if WebSocket disconnects

### Ride Status Updates
- Status transitions follow strict business rules
- All participants receive updates automatically
- ETA is included where relevant
- Driver info is shared when ride is assigned

### Location Updates
- Drivers send location updates periodically when online
- During active rides, location is shared with rider in real-time
- Used for ETA calculations and route optimization

### Error Handling
- All events include proper error responses
- Authentication failures disconnect the client
- Business rule violations return descriptive errors
- Network issues trigger automatic reconnection logic

### Security
- All events require authentication
- Room-based authorization prevents unauthorized access
- Rate limiting on chat and location updates
- Input validation on all payloads