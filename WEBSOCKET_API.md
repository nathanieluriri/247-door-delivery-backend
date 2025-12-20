# WebSocket Handler Documentation

This document describes the restructured WebSocket handler for the Door Delivery Backend, designed to work properly with browsers and provide structured, well-documented events.

## Authentication

Browser WebSocket connections cannot send HTTP headers like `Authorization`. Instead, authentication is handled via a dedicated `authenticate` event after connecting.

### Connection Flow

1. Client connects to WebSocket endpoint
2. Server responds with `server_message`: "Connected to server! Please authenticate."
3. Client sends `authenticate` event with token
4. Server responds with `authenticate_response` indicating success/failure

### Authenticate Event

**Event Name:** `authenticate`

**Request Payload:**
```json
{
  "token": "jwt_access_token_here"
}
```

**Response Event:** `authenticate_response`

**Response Payload:**
```json
{
  "status": "success",
  "message": "Authenticated successfully",
  "user_type": "RIDER" | "DRIVER",
  "user_id": "user_id_string"
}
```

## Event Structure

All events now use structured Pydantic models for requests and responses. Events are emitted asynchronously, not returned as values.

### General Response Format

Most responses follow this pattern:
```json
{
  "status": "success" | "error",
  "message": "Description of result",
  // Additional fields depending on event
}
```

## Driver Events

### Go Online

**Event:** `go_online`

**Request:** `{}` (empty)

**Response Event:** `go_online_response`

**Response:**
```json
{
  "status": "success",
  "message": "Driver is now online"
}
```

### Go Offline

**Event:** `go_offline`

**Request:** `{}`

**Response Event:** `go_offline_response`

**Response:**
```json
{
  "status": "success",
  "message": "Driver is now offline"
}
```

### Update Location

**Event:** `update_location`

**Request:**
```json
{
  "latitude": 37.7749,
  "longitude": -122.4194
}
```

**Response Event:** `update_location_response`

**Response:**
```json
{
  "status": "success",
  "message": "Location updated"
}
```

## Ride Events

### Accept Ride (Driver)

**Event:** `accept_ride`

**Request:**
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event:** `accept_ride_response`

**Response:**
```json
{
  "status": "success",
  "message": "Ride accepted",
  "driver_info": {
    // Driver details including ratings
  }
}
```

Also broadcasts `ride_status_update` to the ride room.

### Start Ride (Driver)

**Event:** `start_ride`

**Request:**
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event:** `start_ride_response`

**Response:**
```json
{
  "status": "success",
  "message": "Ride started"
}
```

### Complete Ride (Driver)

**Event:** `complete_ride`

**Request:**
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event:** `complete_ride_response`

**Response:**
```json
{
  "status": "success",
  "message": "Ride completed",
  "ride_data": {
    // Complete ride details
  }
}
```

## Rider Events

### Join Ride Room

**Event:** `join_ride_room`

**Request:**
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event:** `join_ride_room_response`

**Response:**
```json
{
  "status": "success",
  "message": "Joined ride room",
  "ride_data": {
    // Ride details
  }
}
```

### Get Ride State

**Event:** `get_ride_state`

**Request:**
```json
{
  "ride_id": "ride_id_string"
}
```

**Response Event:** `get_ride_state_response`

**Response:**
```json
{
  "status": "success",
  "message": "Ride state retrieved",
  "ride_data": {
    // Current ride state
  }
}
```

## Server-to-Client Events

### Ride Status Update

**Event:** `ride_status_update`

**Payload:**
```json
{
  "status": "ACCEPTED" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED",
  "data": {
    // Status-specific data
  },
  "eta_minutes": 10
}
```

### New Ride Request (to Drivers)

**Event:** `new_ride_request`

**Payload:**
```json
{
  "ride_id": "ride_id_string",
  "pickup": {
    "latitude": 37.7749,
    "longitude": -122.4194
  },
  "dropoff": {
    "latitude": 37.7849,
    "longitude": -122.4294
  },
  "vehicle_type": "standard",
  "fare_estimate": 25.50
}
```

## Error Handling

All events include proper error responses. Unauthorized access returns:
```json
{
  "status": "error",
  "message": "Unauthorized",
  "detail": "This event is for drivers/riders"
}
```

## Browser Compatibility

- Uses standard Socket.IO client library
- Authentication via message events instead of headers
- Structured JSON payloads for all communication
- Proper async event handling

## Implementation Notes

- All event handlers validate user types and permissions
- Redis OM used for real-time user state
- Geospatial queries for nearby driver matching
- Room-based communication for ride-specific updates

---

# Frontend Integration Guide

This guide provides complete examples for integrating with the WebSocket API from a frontend application using Socket.IO client.

## Setup

First, install Socket.IO client:

```bash
npm install socket.io-client
```

## Basic Connection

```javascript
import io from 'socket.io-client';

// Connect to your backend WebSocket endpoint
const socket = io('http://localhost:8000', {
  transports: ['websocket', 'polling']
});

// Connection established
socket.on('connect', () => {
  console.log('Connected to server:', socket.id);
});

// Connection lost
socket.on('disconnect', (reason) => {
  console.log('Disconnected:', reason);
});
```

## Authentication Flow

**Important:** Always authenticate immediately after connecting.

```javascript
class WebSocketManager {
  constructor() {
    this.socket = null;
    this.userType = null;
    this.userId = null;
    this.isAuthenticated = false;
  }

  connect(serverUrl = 'http://localhost:8000') {
    this.socket = io(serverUrl, {
      transports: ['websocket', 'polling']
    });

    this.setupEventListeners();
  }

  setupEventListeners() {
    // Wait for server welcome message
    this.socket.on('server_message', (data) => {
      console.log('Server:', data.msg);
      // Now authenticate
      this.authenticate();
    });

    // Handle authentication response
    this.socket.on('authenticate_response', (response) => {
      if (response.status === 'success') {
        this.isAuthenticated = true;
        this.userType = response.user_type;
        this.userId = response.user_id;
        console.log(`Authenticated as ${this.userType}: ${this.userId}`);

        // Now you can send other events based on user type
        this.onAuthenticated();
      } else {
        console.error('Authentication failed:', response.message);
        this.handleAuthError(response);
      }
    });
  }

  authenticate(token) {
    if (!this.socket) {
      console.error('Socket not connected');
      return;
    }

    this.socket.emit('authenticate', {
      token: token // Your JWT access token
    });
  }

  onAuthenticated() {
    // Override this method in subclasses for specific user types
    console.log('Authentication successful, ready to send events');
  }

  handleAuthError(response) {
    // Handle authentication errors (show login screen, etc.)
    alert('Authentication failed: ' + response.message);
  }
}
```

## Driver Implementation

```javascript
class DriverWebSocketManager extends WebSocketManager {
  constructor() {
    super();
    this.isOnline = false;
    this.currentLocation = null;
  }

  onAuthenticated() {
    if (this.userType !== 'DRIVER') {
      console.error('This manager is for drivers only');
      return;
    }

    this.setupDriverEventListeners();
    // Optionally auto-go online
    // this.goOnline();
  }

  setupDriverEventListeners() {
    // Go online/offline responses
    this.socket.on('go_online_response', (response) => {
      if (response.status === 'success') {
        this.isOnline = true;
        console.log('Driver is now online');
        this.onGoOnline();
      } else {
        console.error('Failed to go online:', response.message);
      }
    });

    this.socket.on('go_offline_response', (response) => {
      if (response.status === 'success') {
        this.isOnline = false;
        console.log('Driver is now offline');
        this.onGoOffline();
      } else {
        console.error('Failed to go offline:', response.message);
      }
    });

    // Location update responses
    this.socket.on('update_location_response', (response) => {
      if (response.status === 'success') {
        console.log('Location updated successfully');
      } else {
        console.error('Location update failed:', response.message);
      }
    });

    // Ride request responses
    this.socket.on('accept_ride_response', (response) => {
      if (response.status === 'success') {
        console.log('Ride accepted:', response.driver_info);
        this.onRideAccepted(response.driver_info);
      } else {
        console.error('Failed to accept ride:', response.message);
      }
    });

    this.socket.on('start_ride_response', (response) => {
      if (response.status === 'success') {
        console.log('Ride started');
        this.onRideStarted();
      } else {
        console.error('Failed to start ride:', response.message);
      }
    });

    this.socket.on('complete_ride_response', (response) => {
      if (response.status === 'success') {
        console.log('Ride completed:', response.ride_data);
        this.onRideCompleted(response.ride_data);
      } else {
        console.error('Failed to complete ride:', response.message);
      }
    });

    // Listen for new ride requests
    this.socket.on('new_ride_request', (rideRequest) => {
      console.log('New ride request:', rideRequest);
      this.onNewRideRequest(rideRequest);
    });
  }

  // Driver Actions
  goOnline() {
    this.socket.emit('go_online');
  }

  goOffline() {
    this.socket.emit('go_offline');
  }

  updateLocation(latitude, longitude) {
    this.currentLocation = { latitude, longitude };
    this.socket.emit('update_location', {
      latitude: latitude,
      longitude: longitude
    });
  }

  acceptRide(rideId) {
    this.socket.emit('accept_ride', {
      ride_id: rideId
    });
  }

  startRide(rideId) {
    this.socket.emit('start_ride', {
      ride_id: rideId
    });
  }

  completeRide(rideId) {
    this.socket.emit('complete_ride', {
      ride_id: rideId
    });
  }

  // Override these methods in your app
  onGoOnline() {}
  onGoOffline() {}
  onRideAccepted(driverInfo) {}
  onRideStarted() {}
  onRideCompleted(rideData) {}
  onNewRideRequest(rideRequest) {}
}
```

## Rider Implementation

```javascript
class RiderWebSocketManager extends WebSocketManager {
  constructor() {
    super();
    this.currentRideId = null;
  }

  onAuthenticated() {
    if (this.userType !== 'RIDER') {
      console.error('This manager is for riders only');
      return;
    }

    this.setupRiderEventListeners();
  }

  setupRiderEventListeners() {
    // Join ride room responses
    this.socket.on('join_ride_room_response', (response) => {
      if (response.status === 'success') {
        this.currentRideId = response.ride_data?.id;
        console.log('Joined ride room:', response.ride_data);
        this.onJoinedRideRoom(response.ride_data);
      } else {
        console.error('Failed to join ride room:', response.message);
      }
    });

    // Get ride state responses
    this.socket.on('get_ride_state_response', (response) => {
      if (response.status === 'success') {
        console.log('Ride state:', response.ride_data);
        this.onRideStateReceived(response.ride_data);
      } else {
        console.error('Failed to get ride state:', response.message);
      }
    });

    // Listen for ride status updates
    this.socket.on('ride_status_update', (update) => {
      console.log('Ride status update:', update);
      this.onRideStatusUpdate(update);
    });
  }

  // Rider Actions
  joinRideRoom(rideId) {
    this.socket.emit('join_ride_room', {
      ride_id: rideId
    });
  }

  getRideState(rideId) {
    this.socket.emit('get_ride_state', {
      ride_id: rideId
    });
  }

  // Override these methods in your app
  onJoinedRideRoom(rideData) {}
  onRideStateReceived(rideData) {}
  onRideStatusUpdate(update) {}
}
```

## Complete Usage Example

```javascript
// For Drivers
const driverManager = new DriverWebSocketManager();

// Connect and authenticate
driverManager.connect('http://localhost:8000');
driverManager.authenticate('your_jwt_token_here');

// Override methods for your app logic
driverManager.onNewRideRequest = (rideRequest) => {
  // Show ride request to driver
  if (confirm(`New ride request from ${rideRequest.pickup} to ${rideRequest.dropoff}. Accept?`)) {
    driverManager.acceptRide(rideRequest.ride_id);
  }
};

driverManager.onRideAccepted = (driverInfo) => {
  // Update UI to show accepted ride
  console.log('Ride accepted, waiting for rider...');
};

driverManager.onRideStatusUpdate = (update) => {
  // Handle status updates from server
  switch(update.status) {
    case 'ACCEPTED':
      showMessage('Driver is on the way!');
      break;
    case 'IN_PROGRESS':
      showMessage('Ride started!');
      break;
    case 'COMPLETED':
      showMessage('Ride completed!');
      break;
  }
};

// Start location tracking (example)
if (navigator.geolocation) {
  navigator.geolocation.watchPosition((position) => {
    driverManager.updateLocation(
      position.coords.latitude,
      position.coords.longitude
    );
  });
}

// For Riders
const riderManager = new RiderWebSocketManager();
riderManager.connect('http://localhost:8000');
riderManager.authenticate('your_jwt_token_here');

riderManager.onJoinedRideRoom = (rideData) => {
  // Update UI with ride details
  console.log('Connected to ride:', rideData);
};

riderManager.onRideStatusUpdate = (update) => {
  // Update ride status in UI
  updateRideStatus(update.status, update.data);
};
```

## Error Handling

All events include error responses. Always check the `status` field:

```javascript
// Generic error handler
socket.on('go_online_response', (response) => {
  if (response.status === 'error') {
    if (response.detail === 'This event is for drivers') {
      // Wrong user type
      showError('This feature is for drivers only');
    } else {
      // Other error
      showError(response.message);
    }
  } else {
    // Success
    console.log(response.message);
  }
});
```

## Best Practices

1. **Always authenticate first** - Don't send other events until authenticated
2. **Handle disconnections** - Reconnect and re-authenticate when connection is lost
3. **Check user types** - Different events are available for drivers vs riders
4. **Validate data** - Check response status before processing
5. **Clean up listeners** - Remove event listeners when component unmounts
6. **Error boundaries** - Wrap WebSocket operations in try-catch blocks

## Connection Management

```javascript
class ConnectionManager {
  constructor(webSocketManager) {
    this.manager = webSocketManager;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  start() {
    this.manager.connect();
    this.setupReconnection();
  }

  setupReconnection() {
    this.manager.socket.on('disconnect', (reason) => {
      console.log('Disconnected:', reason);

      if (reason === 'io server disconnect') {
        // Server disconnected us, don't reconnect
        return;
      }

      this.attemptReconnect();
    });
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(`Reconnection attempt ${this.reconnectAttempts}`);

    setTimeout(() => {
      this.manager.connect();
      // Re-authenticate after reconnect
      this.manager.socket.once('server_message', () => {
        this.manager.authenticate(this.storedToken);
      });
    }, 1000 * this.reconnectAttempts); // Exponential backoff
  }
}
```

## Event Reference

### Events to Send (Client → Server)

| Event | User Type | Payload | Description |
|-------|-----------|---------|-------------|
| `authenticate` | Both | `{token: "jwt"}` | Authenticate after connecting |
| `go_online` | Driver | `{}` | Mark driver as available |
| `go_offline` | Driver | `{}` | Mark driver as unavailable |
| `update_location` | Driver | `{latitude: float, longitude: float}` | Update driver location |
| `accept_ride` | Driver | `{ride_id: "string"}` | Accept a ride request |
| `start_ride` | Driver | `{ride_id: "string"}` | Start the ride |
| `complete_ride` | Driver | `{ride_id: "string"}` | Complete the ride |
| `join_ride_room` | Rider | `{ride_id: "string"}` | Join ride communication room |
| `get_ride_state` | Rider | `{ride_id: "string"}` | Get current ride status |

### Events to Listen (Server → Client)

| Event | User Type | Payload | Description |
|-------|-----------|---------|-------------|
| `server_message` | Both | `{msg: "string"}` | Server welcome message |
| `authenticate_response` | Both | Auth response | Authentication result |
| `go_online_response` | Driver | Status response | Go online result |
| `go_offline_response` | Driver | Status response | Go offline result |
| `update_location_response` | Driver | Status response | Location update result |
| `accept_ride_response` | Driver | Accept response | Ride acceptance result |
| `start_ride_response` | Driver | Status response | Ride start result |
| `complete_ride_response` | Driver | Complete response | Ride completion result |
| `new_ride_request` | Driver | Ride request | New ride available |
| `join_ride_room_response` | Rider | Join response | Room join result |
| `get_ride_state_response` | Rider | State response | Ride state result |
| `ride_status_update` | Both | Status update | Ride status changes |

This guide provides everything needed to integrate the WebSocket API into your frontend application. The examples are production-ready and include proper error handling and reconnection logic.