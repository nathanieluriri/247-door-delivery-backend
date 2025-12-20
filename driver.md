# Driver API Documentation

This document provides comprehensive documentation for all REST API endpoints and WebSocket events available to drivers in the Door Delivery Backend system.

## Authentication Flow

Drivers can authenticate through Google OAuth or traditional email/password signup.

### Google OAuth Authentication

**Step 1: Redirect to Google**
```
GET /api/v1/drivers/google/auth
```
- Redirects user to Google OAuth login
- Returns redirect URL for Google authentication

**Step 2: Handle Google Callback**
```
GET /api/v1/drivers/auth/callback
```
- Handles the callback from Google OAuth
- Creates or authenticates driver account
- Returns driver data with authentication tokens

### Traditional Authentication

**Signup**
```
POST /api/v1/drivers/signup
Content-Type: application/json

{
  "email": "driver@example.com",
  "password": "password123"
}
```
- Creates new driver account
- Password must be at least 8 characters
- Returns driver data (password excluded)

**Login**
```
POST /api/v1/drivers/login
Content-Type: application/json

{
  "email": "driver@example.com",
  "password": "password123"
}
```
- Authenticates existing driver
- Returns driver data with tokens

**Token Refresh**
```
POST /api/v1/drivers/refesh
Authorization: Bearer <expired_access_token>
Content-Type: application/json

{
  "refresh_token": "valid_refresh_token"
}
```
- Refreshes expired access token
- Requires expired access token in header and valid refresh token in body

## Profile Management

**Get Driver Profile**
```
GET /api/v1/drivers/me
Authorization: Bearer <access_token>
```
- Returns authenticated driver's profile information

**Update Driver Profile**
```
PATCH /api/v1/drivers/profile
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "name": "John Doe",
  "phone": "+1234567890",
  "vehicleType": "SEDAN"
}
```
- Updates driver profile information
- Requires driver role verification and active account status

**Delete Driver Account**
```
DELETE /api/v1/drivers/account
Authorization: Bearer <access_token>
```
- Permanently deletes driver account
- Requires driver role verification and active account status

## Rating System

**View Own Rating**
```
GET /api/v1/drivers/rating
Authorization: Bearer <access_token>
```
- Returns driver's current rating and rating history

**View Rider Rating**
```
GET /api/v1/drivers/rider/{riderId}/rating
Authorization: Bearer <access_token>
```
- Returns specific rider's rating information

**Rate Rider After Ride**
```
POST /api/v1/drivers/rate/rider
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "userId": "rider_id",
  "rating": 5,
  "comment": "Great passenger!"
}
```
- Allows driver to rate a rider after completing a ride

## Ride Management

**View Ride History**
```
GET /api/v1/drivers/ride/history
Authorization: Bearer <access_token>
```
- Returns list of all rides completed by the driver
- Includes ride details, earnings, and ratings

## Password Management

**Update Password (Logged In)**
```
PATCH /api/v1/drivers/password-reset
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "currentPassword": "old_password",
  "newPassword": "new_password123"
}
```
- Updates password for authenticated driver

**Request Password Reset**
```
POST /api/v1/drivers/password-reset/request
Content-Type: application/json

{
  "email": "driver@example.com"
}
```
- Initiates password reset process
- Sends reset email to driver

**Confirm Password Reset**
```
PATCH /api/v1/drivers/password-reset/confirm
Content-Type: application/json

{
  "token": "reset_token_from_email",
  "newPassword": "new_password123"
}
```
- Completes password reset with token from email

## WebSocket Events

Drivers use WebSocket connections for real-time communication during rides. All WebSocket events require prior authentication via REST API.

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
    // Driver authenticated, can now use driver events
    console.log(`Authenticated as ${response.user_type}: ${response.user_id}`);
  }
});
```

### Driver Availability

**Go Online**
```javascript
socket.emit('go_online');
```

**Go Online Response**
```javascript
socket.on('go_online_response', (response) => {
  if (response.status === 'success') {
    console.log('Driver is now online and available for rides');
  }
});
```

**Go Offline**
```javascript
socket.emit('go_offline');
```

**Go Offline Response**
```javascript
socket.on('go_offline_response', (response) => {
  if (response.status === 'success') {
    console.log('Driver is now offline');
  }
});
```

### Location Updates

**Update Location**
```javascript
socket.emit('update_location', {
  latitude: 37.7749,
  longitude: -122.4194
});
```

**Location Update Response**
```javascript
socket.on('update_location_response', (response) => {
  if (response.status === 'success') {
    console.log('Location updated successfully');
  }
});
```

### Ride Management

**Accept Ride**
```javascript
socket.emit('accept_ride', {
  ride_id: "ride_id_string"
});
```

**Accept Ride Response**
```javascript
socket.on('accept_ride_response', (response) => {
  if (response.status === 'success') {
    console.log('Ride accepted:', response.driver_info);
    // Ride status updates will now be broadcast to ride room
  }
});
```

**Start Ride**
```javascript
socket.emit('start_ride', {
  ride_id: "ride_id_string"
});
```

**Start Ride Response**
```javascript
socket.on('start_ride_response', (response) => {
  if (response.status === 'success') {
    console.log('Ride started successfully');
  }
});
```

**Complete Ride**
```javascript
socket.emit('complete_ride', {
  ride_id: "ride_id_string"
});
```

**Complete Ride Response**
```javascript
socket.on('complete_ride_response', (response) => {
  if (response.status === 'success') {
    console.log('Ride completed:', response.ride_data);
  }
});
```

### Receiving Ride Requests

**New Ride Request**
```javascript
socket.on('new_ride_request', (rideRequest) => {
  console.log('New ride request:', rideRequest);
  // rideRequest contains: ride_id, pickup, dropoff, vehicle_type, fare_estimate
});
```

### Ride Status Updates

**Ride Status Update**
```javascript
socket.on('ride_status_update', (update) => {
  console.log('Ride status update:', update);
  // update contains: status, data, eta_minutes
  switch(update.status) {
    case 'ACCEPTED':
      // Driver accepted the ride
      break;
    case 'IN_PROGRESS':
      // Ride is in progress
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

## Complete Driver Flow

1. **Authentication**: Driver signs up/logs in via REST API
2. **Go Online**: Driver connects via WebSocket and goes online
3. **Location Updates**: Driver continuously updates location while online
4. **Receive Ride Requests**: Driver receives new ride requests via WebSocket
5. **Accept Ride**: Driver accepts ride request
6. **Start Ride**: Driver starts the ride when passenger is picked up
7. **Complete Ride**: Driver completes ride and rates passenger
8. **View History**: Driver can view completed rides and earnings via REST API

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
- `500 Internal Server Error`: Server error

## Security Requirements

- All REST endpoints require valid JWT access token in Authorization header
- Driver role verification required for driver-specific endpoints
- Account status checks ensure driver account is active
- Passwords must be at least 8 characters
- Rate limiting applied to prevent abuse</content>
<parameter name="filePath">c:\Users\Mr Dashi\Downloads\door-delivery-backend\app\driver.md