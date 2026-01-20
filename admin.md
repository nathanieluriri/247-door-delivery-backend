# Admin API Documentation

This document provides comprehensive documentation for all REST API endpoints available to administrators in the Door Delivery Backend system. Admins have elevated privileges to manage users, rides, and system operations.

## Authentication Flow

Admins authenticate through traditional email/password signup and login.

### Authentication

**Signup (Admin Only)**
```
POST /api/v1/admins/signup
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "password123",
  "permissions": ["USER_MANAGEMENT", "RIDE_MANAGEMENT"]
}
```
- Creates new admin account (requires existing admin token)
- Password must be at least 8 characters
- Returns admin data (password excluded)

**Login**
```
POST /api/v1/admins/login
Content-Type: application/json

{
  "email": "admin@example.com",
  "password": "password123"
}
```
- Authenticates admin account
- Returns admin data with authentication tokens

**Token Refresh**
```
POST /api/v1/admins/refresh
Authorization: Bearer <expired_access_token>
Content-Type: application/json

{
  "refresh_token": "valid_refresh_token"
}
```
- Refreshes expired access token
- Requires expired access token in header and valid refresh token in body

## Profile Management

**List Admins**
```
GET /api/v1/admins/{start}/{stop}
Authorization: Bearer <admin_access_token>
```
- Returns paginated list of all admins
- Requires admin role and permissions verification

**Get Admin Profile**
```
GET /api/v1/admins/profile
Authorization: Bearer <admin_access_token>
```
- Returns authenticated admin's profile information

**Update Admin Profile**
```
PATCH /api/v1/admins/profile
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "name": "Admin Name",
  "phone": "+1234567890"
}
```
- Updates admin profile information
- Requires admin role and permissions verification

**Delete Admin Account**
```
DELETE /api/v1/admins/account
Authorization: Bearer <admin_access_token>
```
- Permanently deletes admin account
- Requires admin role verification

## Driver Management

**List All Drivers**
```
GET /api/v1/admins/drivers/
Authorization: Bearer <admin_access_token>
```
- Returns paginated list of all registered drivers
- Requires admin role and permissions verification

**Get Specific Driver**
```
GET /api/v1/admins/driver/{driverId}
Authorization: Bearer <admin_access_token>
```
- Returns detailed information for specific driver

**Ban Driver**
```
PATCH /api/v1/admins/ban/driver/{driverId}
Authorization: Bearer <admin_access_token>
```
- Bans driver from using the platform
- Sets driver account status to BANNED
- Asynchronous operation via Celery worker

**Approve Driver**
```
PATCH /api/v1/admins/approve/driver/{driverId}
Authorization: Bearer <admin_access_token>
```
- Approves driver to use the platform
- Sets driver account status to ACTIVE
- Required before drivers can accept rides

## Rider Management

**List All Riders**
```
GET /api/v1/admins/riders/
Authorization: Bearer <admin_access_token>
```
- Returns paginated list of all registered riders
- Requires admin role and permissions verification

**Get Specific Rider**
```
GET /api/v1/admins/rider/{riderId}
Authorization: Bearer <admin_access_token>
```
- Returns detailed information for specific rider

**Ban Rider**
```
PATCH /api/v1/admins/ban/rider/{riderId}
Authorization: Bearer <admin_access_token>
```
- Bans rider from using the platform
- Sets rider account status to BANNED
- Asynchronous operation via Celery worker

## Ride Management

**Create Ride for User**
```
POST /api/v1/admins/ride/{userId}
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "pickup": "place_id_string",
  "destination": "place_id_string",
  "vehicleType": "SEDAN",
  "stops": ["place_id_1", "place_id_2"]
}
```
- Creates a ride for a specific user (admin function)
- Calculates fare based on distance and vehicle type
- Returns complete ride data

**Get Rides by Rider**
```
GET /api/v1/admins/ride/{riderId}
Authorization: Bearer <admin_access_token>
```
- Returns all rides for a specific rider

**Get Rides by Driver**
```
GET /api/v1/admins/ride/{driverId}
Authorization: Bearer <admin_access_token>
```
- Returns all rides for a specific driver

**Cancel Ride**
```
PATCH /api/v1/admins/ride/{rideId}
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "rideStatus": "CANCELLED"
}
```
- Cancels a ride (admin override)
- Updates ride status to cancelled

## Invoice Management

**Generate Invoice**
```
POST /api/v1/admins/invoice/{rideId}
Authorization: Bearer <admin_access_token>
```
- Generates invoice for completed ride
- Uses Stripe for payment processing
- Returns invoice data

**Get Invoice**
```
GET /api/v1/admins/invoice/{rideId}
Authorization: Bearer <admin_access_token>
```
- Retrieves invoice data for a ride
- Returns Stripe invoice information

## Password Management

**Update Password (Logged In)**
```
PATCH /api/v1/admins/password-reset
Authorization: Bearer <admin_access_token>
Content-Type: application/json

{
  "currentPassword": "old_password",
  "newPassword": "new_password123"
}
```
- Updates password for authenticated admin

**Request Password Reset**
```
POST /api/v1/admins/password-reset/request
Content-Type: application/json

{
  "email": "admin@example.com"
}
```
- Initiates password reset process
- Sends reset email to admin

**Confirm Password Reset**
```
PATCH /api/v1/admins/password-reset/confirm
Content-Type: application/json

{
  "token": "reset_token_from_email",
  "newPassword": "new_password123"
}
```
- Completes password reset with token from email

## Admin Workflow Examples

### Onboarding New Driver
1. **Create Driver Account**: Driver signs up via `/api/v1/drivers/signup`
2. **Review Driver**: Admin reviews driver details via `/api/v1/admins/driver/{driverId}`
3. **Approve Driver**: Admin approves via `/api/v1/admins/approve/driver/{driverId}`
4. **Driver Active**: Driver can now go online and accept rides

### Managing Ride Disputes
1. **View Ride Details**: Admin checks ride via `/api/v1/admins/ride/{riderId}` or `/api/v1/admins/ride/{driverId}`
2. **Generate Invoice**: Admin creates invoice via `/api/v1/admins/invoice/{rideId}`
3. **Cancel if Needed**: Admin can cancel ride via `/api/v1/admins/ride/{rideId}`

### User Management
1. **Monitor Users**: Admin lists all users via `/api/v1/admins/drivers/` and `/api/v1/admins/riders/`
2. **Ban Problematic Users**: Admin bans via `/api/v1/admins/ban/driver/{driverId}` or `/api/v1/admins/ban/rider/{riderId}`
3. **Review Actions**: All admin actions are logged for audit purposes

## Security & Permissions

**Role-Based Access Control**
- All admin endpoints require valid admin JWT token
- Admin role verification on all endpoints
- Account status checks ensure admin account is active
- Permission-based access for sensitive operations

**Audit Logging**
- All admin actions are logged via `log_what_admin_does` middleware
- Logs include admin ID, action performed, and timestamp
- Critical for compliance and security monitoring

**Asynchronous Operations**
- User banning operations use Celery workers for reliability
- Prevents blocking during bulk operations
- Provides better user experience

## Error Handling

All API endpoints return standardized error responses:
```json
{
  "status_code": 400,
  "detail": "Error description"
}
```

Common admin-specific errors:
- `403 Forbidden`: Insufficient permissions for operation
- `404 Not Found`: User or ride not found
- `409 Conflict`: Operation conflicts with current state
- `422 Unprocessable Entity`: Invalid request data

## Best Practices

**Admin Operations**
- Always verify user identity before performing actions
- Use pagination for large user lists
- Review audit logs regularly
- Test operations in staging environment first

**Security**
- Use strong, unique passwords
- Enable two-factor authentication when available
- Regularly rotate access tokens
- Monitor for suspicious activity

**Performance**
- Use appropriate pagination limits
- Cache frequently accessed data
- Monitor API usage patterns
- Implement rate limiting for bulk operations</content>
