# Driver API Documentation

This document provides comprehensive documentation for all REST API endpoints and SSE streams available to drivers in the Door Delivery Backend system.

## Authentication Flow

Drivers can authenticate through Google OAuth or traditional email/password signup.

### Google OAuth Authentication

**Step 1: Redirect to Google**
```
GET /api/v1/drivers/google/auth
```
- Redirects user to Google OAuth login
- Returns redirect URL for Google authentication

Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | empty | yes | Redirect response |

**Step 2: Handle Google Callback**
```
GET /api/v1/drivers/auth/callback
```
- Handles the callback from Google OAuth
- Creates or authenticates driver account
- Returns driver data with authentication tokens

Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.email | string (email) | yes | Driver email |
| data.password | string or binary | yes | Driver password value |
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.stripeAccountId | string or null | no | Stripe account id |
| data.vehicleType | string or null | no | Vehicle type (CAR, MOTOR_BIKE) |
| data.vehicleMake | string or null | no | Vehicle make |
| data.vehicleModel | string or null | no | Vehicle model |
| data.vehicleColor | string or null | no | Vehicle color |
| data.vehiclePlateNumber | string or null | no | Plate number |
| data.vehicleYear | integer or null | no | Vehicle year |
| data.profileComplete | boolean | yes | True when vehicle details are complete |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Driver id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

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

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| email | string (email) | yes | Driver email |
| password | string or binary | yes | Password |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.email | string (email) | yes | Driver email |
| data.password | string or binary | yes | Driver password value |
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.stripeAccountId | string or null | no | Stripe account id |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Driver id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

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

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| email | string (email) | yes | Driver email |
| password | string or binary | yes | Password |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.email | string (email) | yes | Driver email |
| data.password | string or binary | yes | Driver password value |
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.stripeAccountId | string or null | no | Stripe account id |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Driver id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

**Token Refresh**
```
POST /api/v1/drivers/refresh
Authorization: Bearer <expired_access_token>
Content-Type: application/json

{
  "refresh_token": "valid_refresh_token"
}
```
- Refreshes expired access token
- Requires expired access token in header and valid refresh token in body

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| refresh_token | string or null | no | Refresh token |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.email | string (email) | yes | Driver email |
| data.password | string or binary | yes | Driver password value |
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.stripeAccountId | string or null | no | Stripe account id |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Driver id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

## Profile Management

**Get Driver Profile**
```
GET /api/v1/drivers/me
Authorization: Bearer <access_token>
```
- Returns authenticated driver's profile information

Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.email | string (email) | yes | Driver email |
| data.password | string or binary | yes | Driver password value |
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.stripeAccountId | string or null | no | Stripe account id |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Driver id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

**Update Driver Profile**
```
PATCH /api/v1/drivers/profile
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "firstName": "John",
  "lastName": "Doe",
  "last_updated": 1700000000
}
```
- Updates driver profile information
- Requires driver role verification and active account status

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| firstName | string or null | no | First name |
| lastName | string or null | no | Last name |
| last_updated | integer | no | Unix timestamp |

**Update Driver Vehicle Details**
```
PUT /api/v1/drivers/vehicle
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "vehicleType": "CAR",
  "vehicleMake": "Toyota",
  "vehicleModel": "Corolla",
  "vehicleColor": "Blue",
  "vehiclePlateNumber": "ABC-1234",
  "vehicleYear": 2018
}
```
- Required before updating live location or receiving ride requests
- Vehicle year minimum is controlled by admin configuration (default 2002)

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| vehicleType | string | yes | Vehicle type (CAR, MOTOR_BIKE) |
| vehicleMake | string | yes | Vehicle make |
| vehicleModel | string | yes | Vehicle model |
| vehicleColor | string | yes | Vehicle color |
| vehiclePlateNumber | string | yes | Plate number |
| vehicleYear | integer | yes | Vehicle year |

**Update Driver Location**
```
POST /api/v1/drivers/location
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "latitude": 6.5244,
  "longitude": 3.3792,
  "accuracy_m": 12,
  "timestamp": 1700000000
}
```
- Updates driver live location for ride matching
- Requires vehicle details to be set

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| latitude | number | yes | Latitude |
| longitude | number | yes | Longitude |
| accuracy_m | number or null | no | GPS accuracy in meters |
| timestamp | integer | no | Unix timestamp |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**Delete Driver Account**
```
DELETE /api/v1/drivers/account
Authorization: Bearer <access_token>
```
- Permanently deletes driver account
- Requires driver role verification and active account status


Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

## Rating System

**View Own Rating**
```
GET /api/v1/drivers/rating
Authorization: Bearer <access_token>
```
- Returns driver's current rating and rating history


Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**View Rider Rating**
```
GET /api/v1/drivers/rider/{riderId}/rating
Authorization: Bearer <access_token>
```
- Returns specific rider's rating information

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| riderId | string | yes | Rider id |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**Rate Rider After Ride**
```
POST /api/v1/drivers/rate/rider
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "rideId": "ride_id",
  "userId": "rider_id",
  "rating": 5
}
```
- Allows driver to rate a rider after completing a ride

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| rideId | string | yes | Ride id |
| userId | string | yes | Rider id |
| rating | integer (1-5) | yes | Rating value |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

## Ride Management

**Accept Ride**
```
POST /api/v1/drivers/ride/{ride_id}/accept
Authorization: Bearer <access_token>
```
- Accepts a ride request and assigns the driver

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| ride_id | string | yes | Ride id |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**Retrieve Ride Details**
```
POST /api/v1/drivers/ride/{ride_id}
Authorization: Bearer <access_token>
```
- Returns ride details for a specific ride

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| ride_id | string | yes | Ride id |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**View Ride History**
```
GET /api/v1/drivers/ride/history
Authorization: Bearer <access_token>
```
- Returns list of all rides completed by the driver
- Includes ride details, earnings, and ratings


Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

## Password Management

**Update Password (Logged In)**
```
PATCH /api/v1/drivers/password-reset
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "password": "new_password123",
  "last_updated": 1700000000
}
```
- Updates password for authenticated driver

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| password | string or binary or null | no | New password |
| last_updated | integer | no | Unix timestamp |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

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

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| email | string (email) | yes | Driver email |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.resetToken | string | yes | Password reset token |

**Confirm Password Reset**
```
PATCH /api/v1/drivers/password-reset/confirm
Content-Type: application/json

{
  "otp": "123456",
  "resetToken": "reset_token_from_email",
  "password": "new_password123"
}
```
- Completes password reset with OTP and reset token

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| otp | string | yes | One-time passcode |
| resetToken | string | yes | Password reset token |
| password | string | yes | New password |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

## SSE Streams

Drivers receive real-time updates via Server-Sent Events (SSE). Streams require the `Authorization: Bearer <token>` header and deliver events until they are acknowledged.

### Connect to the driver stream
```
GET /api/v1/sse/driver/stream
```

Optional query params:
- `event_types`: repeatable filter (e.g. `event_types=ride_request&event_types=ride_status_update`)
- `ride_id`: only emit events for a specific ride

Schema Fields
Query Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| ride_id | string or null | no | Filter by ride id |
| event_types | array[string] or null | no | Filter by event type |
| vehicle_type | string or null | no | Driver vehicle type for ride_request matching |
| latitude | number or null | no | Driver latitude for ride_request matching |
| longitude | number or null | no | Driver longitude for ride_request matching |
| radius_km | number or null | no | Driver match radius (defaults to 5km) |

Response Stream
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| id | string | yes | SSE event id |
| event | string | yes | SSE event name |
| data.id | string | yes | Event id |
| data.event | string | yes | Event name |
| data.data | object | yes | Event payload |
| data.createdAt | integer | yes | Unix timestamp |

### Driver event stream
```
GET /api/v1/drivers/ride/events
Authorization: Bearer <access_token>
```
- Streams driver ride notifications
- Only the latest active driver subscription receives `ride_request` events
- `ride_request` events are filtered by `vehicle_type` and distance to pickup

Schema Fields
Response Stream
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| id | string | yes | SSE event id |
| event | string | yes | SSE event name |
| data.id | string | yes | Event id |
| data.event | string | yes | Event name |
| data.data | object | yes | Event payload |
| data.createdAt | integer | yes | Unix timestamp |

### Ride-specific stream
```
GET /api/v1/drivers/ride/{ride_id}/monitor
```

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| ride_id | string | yes | Ride id |

Response Stream
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| id | string | yes | SSE event id |
| event | string | yes | SSE event name |
| data.id | string | yes | Event id |
| data.event | string | yes | Event name |
| data.data | object | yes | Event payload |
| data.createdAt | integer | yes | Unix timestamp |

### Event format
```
id: <event_id>
event: <event_type>
data: {"id":"...","event":"...","data":{...},"createdAt":1700000000}
```

### Acknowledge events
```
POST /api/v1/sse/driver/ack

{"eventId":"<event_id>"}
```

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| eventId | string | yes | SSE event id |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data | boolean or null | yes | Acknowledgement result |

### curl smoke test
```
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:7860/api/v1/sse/driver/stream?event_types=ride_request"
```

## Complete Driver Flow

1. **Authentication**: Driver signs up/logs in via REST API
2. **Open SSE Stream**: Driver connects to `/api/v1/sse/driver/stream`
3. **Receive Ride Requests**: Driver receives `ride_request` events
4. **Accept Ride**: Driver accepts ride request via REST
5. **Start Ride**: Driver starts the ride when passenger is picked up via REST
6. **Complete Ride**: Driver completes ride and rates passenger via REST
7. **View History**: Driver can view completed rides and earnings via REST API

## Error Handling

All API endpoints return standardized error responses:
```json
{
  "status_code": 400,
  "detail": "Error description"
}
```

SSE stream failures surface as connection errors (401/403) or disconnects. Acknowledgement failures return `404 Not Found` when the event no longer exists.

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
- Rate limiting applied to prevent abuse
