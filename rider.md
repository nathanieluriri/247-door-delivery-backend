# Rider API Documentation

This document provides comprehensive documentation for all REST API endpoints and WebSocket events available to riders in the Door Delivery Backend system.

## Authentication Flow

Riders can authenticate through Google OAuth or traditional email/password signup.

### Google OAuth Authentication

**Step 1: Redirect to Google**
```
GET /api/v1/riders/google/auth
```
- Redirects user to Google OAuth login
- Returns redirect URL for Google authentication

**Step 2: Handle Google Callback**
```
GET /api/v1/riders/auth/callback
```
- Handles the callback from Google OAuth
- Creates or authenticates rider account
- Returns authentication tokens as path of a query parameter to a frontend url specified

### Traditional Authentication

**Signup**
```
POST /api/v1/riders/signup
Content-Type: application/json

{
  "firstName":"nat",
  "lastName":"uriri",
  "email": "rider@example.com",
  "password": "password123"
}
```
- Creates new rider account
- Password must be at least 8 characters
- Returns rider data (password excluded)

**Login**
```
POST /api/v1/riders/login
Content-Type: application/json

{
  "email": "rider@example.com",
  "password": "password123"
}
```
- Authenticates existing rider
- Returns rider data with tokens

**Token Refresh**
```
POST /api/v1/riders/refresh
Authorization: Bearer <expired_access_token>
Content-Type: application/json

{
  "refresh_token": "valid_refresh_token"
}
```
- Refreshes expired access token
- Requires expired access token in header and valid refresh token in body

## Profile Management

**Get Rider Profile**
```
GET /api/v1/riders/me
Authorization: Bearer <access_token>
```
- Returns authenticated rider's profile information

**Update Rider Profile**
```
PATCH /api/v1/riders/profile
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "John Doe",
  "phone": "+1234567890"
}
```
- Updates rider profile information
- Requires rider role verification and active account status

**Delete Rider Account**
```
DELETE /api/v1/riders/account
Authorization: Bearer <access_token>
```
- Permanently deletes rider account
- Requires rider role verification and active account status

## Address Management

**List Saved Addresses**
```
GET /api/v1/riders/addresses
Authorization: Bearer <access_token>
```
- Returns all saved addresses for the rider

**Create Address**
```
POST /api/v1/riders/addresses
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "label": "Home",
  "placeId": "place_id_from_google"
}
```
- Saves a new address for quick access

**Get Specific Address**
```
GET /api/v1/riders/addresses/{addressId}
Authorization: Bearer <access_token>
```
- Returns details for a specific saved address

**Update Address**
```
PATCH /api/v1/riders/addresses/{addressId}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "label": "Work",
  "address": "456 Office Blvd, San Francisco, CA"
}
```
- Updates an existing saved address

**Delete Address**
```
DELETE /api/v1/riders/addresses/{addressId}
Authorization: Bearer <access_token>
```
- Removes a saved address

## Place Services

**Place Autocomplete**
```
GET /api/v1/riders/places/autocomplete?query=San Francisco
Authorization: Bearer <access_token>
```
- Returns place suggestions based on search query
- Uses Google Places API for autocomplete

**Get Place Details**
```
GET /api/v1/riders/places/details/{placeId}
Authorization: Bearer <access_token>
```
- Returns detailed information for a specific place
- Includes coordinates, address, and metadata

**Calculate Fare**
```
POST /api/v1/riders/places/fare
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "origin": "place_id_origin",
  "destination": "place_id_destination",
  "vehicleType": "CAR",
  "stops": ["place_id_stop1", "place_id_stop2"]
}
```
- Calculates estimated fare for a route
- Considers distance, time, vehicle type, and stops

## Rating System

**View Own Rating**
```
GET /api/v1/riders/rating
Authorization: Bearer <access_token>
```
- Returns rider's current rating and summary of ride history

**View Driver Rating**
```
GET /api/v1/riders/driver/{driverId}/rating
Authorization: Bearer <access_token>
```
- Returns specific driver's rating information

**Rate Driver After Ride**
```
POST /api/v1/riders/rate/driver
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "userId": "driver_id",
  "rating": 5,
  "comment": "Excellent driver!"
}
```
- Allows rider to rate a driver after completing a ride

## Ride Management

**Request Ride**
```
POST /api/v1/riders/ride
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "pickup": "place_id_string",
  "destination": "place_id_string",
  "vehicleType": "SEDAN",
  "stops": ["place_id_1", "place_id_2"],
  "paymentMethod": "CARD"
}
```
- Creates a new ride request
- Calculates route and fare automatically
- Matches with nearby available drivers

**Get Ride Details**
```
GET /api/v1/riders/ride/{rideId}
Authorization: Bearer <access_token>
```
- Returns detailed information for a specific ride

**View Ride History**
```
GET /api/v1/riders/ride/history
Authorization: Bearer <access_token>
```
- Returns list of all rides completed by the rider
- Includes ride details, costs, and ratings

**Cancel Ride**
```
PATCH /api/v1/riders/ride/{rideId}
Authorization: Bearer <access_token>
Content-Type: application/json

 
```
- Cancels a pending or in-progress ride
- May incur cancellation fees

## Payment Integration
 
 
 
## Password Management

**Update Password (Logged In)**
```
PATCH /api/v1/riders/password-reset
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "currentPassword": "old_password",
  "newPassword": "new_password123"
}
```
- Updates password for authenticated rider

**Request Password Reset**
```
POST /api/v1/riders/password-reset/request
Content-Type: application/json

{
  "email": "rider@example.com"
}
```
- Initiates password reset process
- Sends reset email to rider

**Confirm Password Reset**
```
PATCH /api/v1/riders/password-reset/confirm
Content-Type: application/json

{
  "token": "reset_token_from_email",
  "newPassword": "new_password123"
}
```
- Completes password reset with token from email

## WebSocket Events

Riders use WebSocket connections for real-time ride tracking and communication. All WebSocket events require prior authentication via REST API.

### Connection & Authentication

**Connect to WebSocket**
```
WebSocket URL: ws://localhost:8000/
```

**Authenticate After Connection**
```javascript
socket.emit('authenticate', {
  token: "jwt_access_token"
});
```

**Authentication Response**
```javascript
socket.on('authenticate_response', (response) => {
  if (response.status === 'success') {
    // Rider authenticated, can now use rider events
    console.log(`Authenticated as ${response.user_type}: ${response.user_id}`);
  }
});
```

### Ride Room Management

**Join Ride Room**
```javascript
socket.emit('join_ride_room', {
  ride_id: "ride_id_string"
});
```

**Join Ride Room Response**
```javascript
socket.on('join_ride_room_response', (response) => {
  if (response.status === 'success') {
    console.log('Joined ride room:', response.ride_data);
    // Now receives real-time updates for this ride
  }
});
```

**Get Ride State**
```javascript
socket.emit('get_ride_state', {
  ride_id: "ride_id_string"
});
```

**Get Ride State Response**
```javascript
socket.on('get_ride_state_response', (response) => {
  if (response.status === 'success') {
    console.log('Current ride state:', response.ride_data);
  }
});
```

### Ride Status Updates

**Ride Status Update**
```javascript
socket.on('ride_status_update', (update) => {
  console.log('Ride status update:', update);
  // update contains: status, data, eta_minutes
  switch(update.status) {
    case 'REQUESTED':
      // Ride requested, waiting for driver
      break;
    case 'ACCEPTED':
      // Driver accepted, on the way
      break;
    case 'ARRIVED':
      // Driver arrived at pickup
      break;
    case 'IN_PROGRESS':
      // Ride started
      break;
    case 'COMPLETED':
      // Ride completed
      break;
    case 'CANCELLED':
      // Ride cancelled
      break;
  }
});
```

## Complete Rider Flow

1. **Authentication**: Rider signs up/logs in via REST API
1. **Real-time Tracking**: Rider connects via WebSocket and joins ride room
2. **Setup Profile**: Rider updates profile and saves favorite addresses
3. **Request Ride**: Rider requests ride with pickup/destination
5. **Monitor Progress**: Rider receives real-time status updates
6. **Complete Ride**: Rider rates driver after ride completion
7. **View History**: Rider can view past rides and receipts

## Ride Request Flow

```javascript
// 1. Calculate fare estimate
const fareEstimate = await fetch('/api/v1/riders/places/fare', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({
    origin: pickupPlaceId,
    destination: dropoffPlaceId,
    vehicleType: 'SEDAN'
  })
});

// 2. Request ride
const rideRequest = await fetch('/api/v1/riders/ride', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({
    pickup: pickupPlaceId,
    destination: dropoffPlaceId,
    vehicleType: 'CAR' 
  })
});

// 3. Connect to WebSocket and join ride room you can connect earlier and then join when ride id is available 
socket.emit('authenticate', { token });
socket.on('authenticate_response', (auth) => {
  if (auth.status === 'success') {
    socket.emit('join_ride_room', { ride_id: rideData.id });
  }
});

// 4. Monitor ride status
socket.on('ride_status_update', (update) => {
  updateRideUI(update.status, update.data);
});
```

## Error Handling

All API endpoints return standardized error responses:
```json
{
  "status_code": 400,
  "detail": "Error description"
}
```

WebSocket events return error responses:
```json
{
  "status": "error",
  "message": "Error description",
  "detail": "Additional error details"
}
```

Common errors:
- `401 Unauthorized`: Invalid or expired token
- `403 Forbidden`: Account banned or insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Ride already in progress
- `422 Unprocessable Entity`: Invalid place IDs or route

## Security Requirements

- All REST endpoints require valid JWT access token in Authorization header
- Rider role verification required for rider-specific endpoints
- Account status checks ensure rider account is active
- Passwords must be at least 8 characters
- Rate limiting applied to prevent abuse

## Best Practices

**Ride Requests**
- Always calculate fare estimate before requesting ride
- Save frequently used addresses for quick access
- Monitor ride status via WebSocket for real-time updates
- Rate drivers promptly after ride completion

**Profile Management**
- Keep contact information up to date
- Save multiple addresses for convenience
- Use strong, unique passwords

**Payment**
- Verify payment methods before ride request
- Check receipts after ride completion
- Report payment issues immediately

**WebSocket Usage**
- Maintain persistent connection during active rides
- Handle reconnection gracefully
- Clean up event listeners when not needed</content>
<parameter name="filePath">c:\Users\Mr Dashi\Downloads\door-delivery-backend\app\rider.md