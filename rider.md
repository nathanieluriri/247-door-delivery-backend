# Rider API Documentation

This document provides comprehensive documentation for all REST API endpoints and SSE streams available to riders in the Door Delivery Backend system.

## Authentication Flow

Riders can authenticate through Google OAuth or traditional email/password signup.

### Google OAuth Authentication

**Step 1: Redirect to Google**
```
GET /api/v1/riders/google/auth
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
GET /api/v1/riders/auth/callback
```
- Handles the callback from Google OAuth
- Creates or authenticates rider account
- Returns authentication tokens as path of a query parameter to a frontend url specified

Schema Fields

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

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

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| firstName | string or null | no | First name |
| lastName | string or null | no | Last name |
| email | string (email) | yes | Rider email |
| password | string or binary | yes | Password |
| loginType | LoginType or null | no | password, passwordless, google |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.email | string (email) | yes | Rider email |
| data.password | string or binary | yes | Rider password value |
| data.loginType | LoginType or null | no | password, passwordless, google |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Rider id |
| data.date_created | integer or null | no | Unix timestamp |
| data.last_updated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

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

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| firstName | string or null | no | First name |
| lastName | string or null | no | Last name |
| email | string (email) | yes | Rider email |
| password | string or binary | yes | Password |
| loginType | LoginType or null | no | password, passwordless, google |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.email | string (email) | yes | Rider email |
| data.password | string or binary | yes | Rider password value |
| data.loginType | LoginType or null | no | password, passwordless, google |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Rider id |
| data.date_created | integer or null | no | Unix timestamp |
| data.last_updated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

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
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.email | string (email) | yes | Rider email |
| data.password | string or binary | yes | Rider password value |
| data.loginType | LoginType or null | no | password, passwordless, google |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Rider id |
| data.date_created | integer or null | no | Unix timestamp |
| data.last_updated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

## Profile Management

**Get Rider Profile**
```
GET /api/v1/riders/profile
Authorization: Bearer <access_token>
```
- Returns authenticated rider's profile information

Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.firstName | string or null | no | First name |
| data.lastName | string or null | no | Last name |
| data.email | string (email) | yes | Rider email |
| data.password | string or binary | yes | Rider password value |
| data.loginType | LoginType or null | no | password, passwordless, google |
| data.accountStatus | AccountStatus or null | no | active, pendingVerification, suspended, banned, deactivated |
| data.id | string or null | no | Rider id |
| data.date_created | integer or null | no | Unix timestamp |
| data.last_updated | integer or null | no | Unix timestamp |
| data.refreshToken | string or null | no | Refresh token |
| data.accessToken | string or null | no | Access token |

**Update Rider Profile**
```
PATCH /api/v1/riders/profile
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "firstName": "John",
  "lastName": "Doe",
  "last_updated": 1700000000
}
```
- Updates rider profile information
- Requires rider role verification and active account status

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| firstName | string or null | no | First name |
| lastName | string or null | no | Last name |
| last_updated | integer | no | Unix timestamp |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**Delete Rider Account**
```
DELETE /api/v1/riders/account
Authorization: Bearer <access_token>
```
- Permanently deletes rider account
- Requires rider role verification and active account status


Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

## Address Management

**List Saved Addresses**
```
GET /api/v1/riders/addresses
Authorization: Bearer <access_token>
```
- Returns all saved addresses for the rider

Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data[].placeId | string | yes | Place id |
| data[].label | string | yes | Address label |
| data[].userId | string | yes | Rider id |
| data[].id | string or null | no | Address id |
| data[].dateCreated | integer or null | no | Unix timestamp |
| data[].lastUpdated | integer or null | no | Unix timestamp |

**Create Address**
```
POST /api/v1/riders/address
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "label": "Home",
  "placeId": "place_id_from_google"
}
```
- Saves a new address for quick access

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| placeId | string | yes | Place id |
| label | string | yes | Address label |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.placeId | string | yes | Place id |
| data.label | string | yes | Address label |
| data.userId | string | yes | Rider id |
| data.id | string or null | no | Address id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |

**Update Address**
```
PATCH /api/v1/riders/address/{addressId}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "label": "Work",
  "placeId": "place_id_from_google",
  "last_updated": 1700000000
}
```
- Updates an existing saved address

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| addressId | string | yes | Address id |

Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| label | string or null | no | Address label |
| placeId | string or null | no | Place id |
| last_updated | integer | no | Unix timestamp |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.placeId | string | yes | Place id |
| data.label | string | yes | Address label |
| data.userId | string | yes | Rider id |
| data.id | string or null | no | Address id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |

**Delete Address**
```
DELETE /api/v1/riders/address/{addressId}
Authorization: Bearer <access_token>
```
- Removes a saved address

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| addressId | string | yes | Address id |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data | boolean (true) or null | yes | Deletion result |

## Place Services

**Place Autocomplete**
```
GET /api/v1/riders/place/autocomplete?input=San%20Francisco&country=us
Authorization: Bearer <access_token>
```
- Returns place suggestions based on search query
- `country` must be one of: us, ng, uk, ca, de, fr, au, jp

Schema Fields
Query Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| input | string | yes | User input text |
| country | string | yes | us, ng, uk, ca, de, fr, au, jp |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data[].description | string | yes | Place description |
| data[].name | string | yes | Place name |
| data[].address | string | yes | Address |
| data[].place_id | string | yes | Place id |
| data[].lat | number | yes | Latitude |
| data[].lng | number | yes | Longitude |

**Allowed Countries Autocomplete**
```
GET /api/v1/riders/place/allowedCountries?input=San%20Francisco&country=us
Authorization: Bearer <access_token>
```
- Alternative autocomplete endpoint with the same query parameters

Schema Fields
Query Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| input | string | yes | User input text |
| country | string | yes | us, ng, uk, ca, de, fr, au, jp |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data[] | array[string] or null | no | List of values |

**Get Place Details**
```
GET /api/v1/riders/place/details?place_id=place_id_from_google
Authorization: Bearer <access_token>
```
- Returns detailed information for a specific place
- Includes coordinates, address, and metadata

Schema Fields
Query Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| place_id | string | yes | Place id |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**Calculate Fare**
```
POST /api/v1/riders/place/calculate-fare
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "pickup": "place_id_origin",
  "destination": "place_id_destination",
  "stops": ["place_id_stop1", "place_id_stop2"]
}
```
- Calculates estimated fare for a route
- Returns distance, duration, and fare details

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| pickup | string | yes | Pickup place id |
| destination | string | yes | Destination place id |
| stops | array[string] or null | no | Intermediate stops |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.origin.latitude | number | yes | Origin latitude |
| data.origin.longitude | number | yes | Origin longitude |
| data.bike_fare | number | yes | Bike fare |
| data.bike.base_fare | number | yes | Base fare |
| data.bike.distance_rate | number | yes | Distance rate |
| data.bike.time_rate | number | yes | Time rate |
| data.bike.seats | integer | yes | Seats |
| data.bike.description | string | yes | Description |
| data.bike.use | string | yes | Use case |
| data.car_fare | number | yes | Car fare |
| data.car.base_fare | number | yes | Base fare |
| data.car.distance_rate | number | yes | Distance rate |
| data.car.time_rate | number | yes | Time rate |
| data.car.seats | integer | yes | Seats |
| data.car.description | string | yes | Description |
| data.car.use | string | yes | Use case |
| data.map.totalDistanceMeters | integer | yes | Total distance |
| data.map.totalDurationSeconds | integer | yes | Total duration |
| data.map.encodedPolyline | string | yes | Encoded polyline |
| data.map.waypointOrder | array[integer] or null | no | Optimized waypoint order |
| data.map.legs[].startAddress | string | yes | Leg start address |
| data.map.legs[].endAddress | string | yes | Leg end address |
| data.map.legs[].distanceMeters | integer | yes | Leg distance |
| data.map.legs[].durationSeconds | integer | yes | Leg duration |

## Rating System

**View Own Rating**
```
GET /api/v1/riders/rating
Authorization: Bearer <access_token>
```
- Returns rider's current rating and summary of ride history


Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**View Driver Rating**
```
GET /api/v1/riders/driver/{driverId}/rating
Authorization: Bearer <access_token>
```
- Returns specific driver's rating information

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| driverId | string | yes | Driver id |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

**Rate Driver After Ride**
```
POST /api/v1/riders/rate/driver
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "rideId": "ride_id",
  "userId": "driver_id",
  "rating": 5
}
```
- Allows rider to rate a driver after completing a ride

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| rideId | string | yes | Ride id |
| userId | string | yes | Driver id |
| rating | integer (1-5) | yes | Rating value |


Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| body | object | no | Response schema not specified in OpenAPI |

## Ride Management

**Request Ride**
```
POST /api/v1/riders/ride/request
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "pickup": "place_id_string",
  "destination": "place_id_string",
  "vehicleType": "CAR",
  "stops": ["place_id_1", "place_id_2"],
  "pickupSchedule": 1700000000
}
```
- Creates a new ride request
- Calculates route and fare automatically
- Matches with nearby available drivers

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| pickup | string | yes | Pickup place id |
| destination | string | yes | Destination place id |
| stops | array[string] or null | no | Intermediate stops |
| vehicleType | VehicleType | yes | MOTOR_BIKE or CAR |
| pickupSchedule | integer or null | no | Unix timestamp |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.pickup | string | yes | Pickup place id |
| data.destination | string | yes | Destination place id |
| data.stops | array[string] or null | no | Intermediate stops |
| data.vehicleType | VehicleType | yes | MOTOR_BIKE or CAR |
| data.pickupSchedule | integer or null | no | Unix timestamp |
| data.paymentStatus | boolean | no | Payment status |
| data.price | number or null | no | Fare amount |
| data.rideStatus | RideStatus or null | no | pendingPayment, findingDriver, arrivingToPickup, drivingToDestination, canceled, completed |
| data.driverId | string or null | no | Driver id |
| data.userId | string | yes | Rider id |
| data.invoiceData | InvoiceData or null | no | Invoice object |
| data.checkoutSessionObject | CheckoutSessionObject or null | no | Stripe checkout session |
| data.stripeEvent | StripeEvent or null | no | Stripe event |
| data.origin | Location or null | no | Origin coordinates |
| data.paymentLink | string or null | no | Payment link |
| data.map | DeliveryRouteResponse or null | no | Route summary |
| data.id | string or null | no | Ride id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |

**Get Ride Details**
```
GET /api/v1/riders/ride/{rideId}
Authorization: Bearer <access_token>
```
- Returns detailed information for a specific ride

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| rideId | string | yes | Ride id |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.pickup | string | yes | Pickup place id |
| data.destination | string | yes | Destination place id |
| data.stops | array[string] or null | no | Intermediate stops |
| data.vehicleType | VehicleType | yes | MOTOR_BIKE or CAR |
| data.pickupSchedule | integer or null | no | Unix timestamp |
| data.paymentStatus | boolean | no | Payment status |
| data.price | number or null | no | Fare amount |
| data.rideStatus | RideStatus or null | no | pendingPayment, findingDriver, arrivingToPickup, drivingToDestination, canceled, completed |
| data.driverId | string or null | no | Driver id |
| data.userId | string | yes | Rider id |
| data.invoiceData | InvoiceData or null | no | Invoice object |
| data.checkoutSessionObject | CheckoutSessionObject or null | no | Stripe checkout session |
| data.stripeEvent | StripeEvent or null | no | Stripe event |
| data.origin | Location or null | no | Origin coordinates |
| data.paymentLink | string or null | no | Payment link |
| data.map | DeliveryRouteResponse or null | no | Route summary |
| data.id | string or null | no | Ride id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |

**View Ride History**
```
GET /api/v1/riders/ride/history
Authorization: Bearer <access_token>
```
- Returns list of all rides completed by the rider
- Includes ride details, costs, and ratings

Schema Fields
Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data[].pickup | string | yes | Pickup place id |
| data[].destination | string | yes | Destination place id |
| data[].stops | array[string] or null | no | Intermediate stops |
| data[].vehicleType | VehicleType | yes | MOTOR_BIKE or CAR |
| data[].pickupSchedule | integer or null | no | Unix timestamp |
| data[].paymentStatus | boolean | no | Payment status |
| data[].price | number or null | no | Fare amount |
| data[].rideStatus | RideStatus or null | no | pendingPayment, findingDriver, arrivingToPickup, drivingToDestination, canceled, completed |
| data[].driverId | string or null | no | Driver id |
| data[].userId | string | yes | Rider id |
| data[].invoiceData | InvoiceData or null | no | Invoice object |
| data[].checkoutSessionObject | CheckoutSessionObject or null | no | Stripe checkout session |
| data[].stripeEvent | StripeEvent or null | no | Stripe event |
| data[].origin | Location or null | no | Origin coordinates |
| data[].paymentLink | string or null | no | Payment link |
| data[].map | DeliveryRouteResponse or null | no | Route summary |
| data[].id | string or null | no | Ride id |
| data[].dateCreated | integer or null | no | Unix timestamp |
| data[].lastUpdated | integer or null | no | Unix timestamp |

**Cancel Ride**
```
PATCH /api/v1/riders/ride/cancel/{rideId}
Authorization: Bearer <access_token>
```
- Cancels a pending ride
- May incur cancellation fees

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| rideId | string | yes | Ride id |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.pickup | string | yes | Pickup place id |
| data.destination | string | yes | Destination place id |
| data.stops | array[string] or null | no | Intermediate stops |
| data.vehicleType | VehicleType | yes | MOTOR_BIKE or CAR |
| data.pickupSchedule | integer or null | no | Unix timestamp |
| data.paymentStatus | boolean | no | Payment status |
| data.price | number or null | no | Fare amount |
| data.rideStatus | RideStatus or null | no | pendingPayment, findingDriver, arrivingToPickup, drivingToDestination, canceled, completed |
| data.driverId | string or null | no | Driver id |
| data.userId | string | yes | Rider id |
| data.invoiceData | InvoiceData or null | no | Invoice object |
| data.checkoutSessionObject | CheckoutSessionObject or null | no | Stripe checkout session |
| data.stripeEvent | StripeEvent or null | no | Stripe event |
| data.origin | Location or null | no | Origin coordinates |
| data.paymentLink | string or null | no | Payment link |
| data.map | DeliveryRouteResponse or null | no | Route summary |
| data.id | string or null | no | Ride id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |

**Share Ride**
```
GET /api/v1/riders/ride/{rideId}/share
Authorization: Bearer <access_token>
```
- Returns a public sharing link for the ride

Schema Fields
Path Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| rideId | string | yes | Ride id |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.pickup | string | yes | Pickup place id |
| data.destination | string | yes | Destination place id |
| data.stops | array[string] or null | no | Intermediate stops |
| data.vehicleType | VehicleType | yes | MOTOR_BIKE or CAR |
| data.pickupSchedule | integer or null | no | Unix timestamp |
| data.paymentStatus | boolean | no | Payment status |
| data.price | number or null | no | Fare amount |
| data.rideStatus | RideStatus or null | no | pendingPayment, findingDriver, arrivingToPickup, drivingToDestination, canceled, completed |
| data.driverId | string or null | no | Driver id |
| data.userId | string | yes | Rider id |
| data.invoiceData | InvoiceData or null | no | Invoice object |
| data.checkoutSessionObject | CheckoutSessionObject or null | no | Stripe checkout session |
| data.stripeEvent | StripeEvent or null | no | Stripe event |
| data.origin | Location or null | no | Origin coordinates |
| data.paymentLink | string or null | no | Payment link |
| data.map | DeliveryRouteResponse or null | no | Route summary |
| data.id | string or null | no | Ride id |
| data.dateCreated | integer or null | no | Unix timestamp |
| data.lastUpdated | integer or null | no | Unix timestamp |

## Payment Integration
 
 
 
## Password Management

**Update Password (Logged In)**
```
PATCH /api/v1/riders/password-reset
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "password": "new_password123",
  "last_updated": 1700000000
}
```
- Updates password for authenticated rider

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
POST /api/v1/riders/password-reset/request
Content-Type: application/json

{
  "email": "rider@example.com"
}
```
- Initiates password reset process
- Sends reset email to rider

Schema Fields
Request Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| email | string (email) | yes | Rider email |

Response Body
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data.resetToken | string | yes | Password reset token |

**Confirm Password Reset**
```
PATCH /api/v1/riders/password-reset/confirm
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

Riders receive real-time updates via Server-Sent Events (SSE). Streams require the `Authorization: Bearer <token>` header and deliver events until they are acknowledged.

### Connect to the rider stream
```
GET /api/v1/sse/rider/stream
```

Optional query params:
- `event_types`: repeatable filter (e.g. `event_types=ride_status_update&event_types=chat_message`)
- `ride_id`: only emit events for a specific ride

Schema Fields
Query Parameters
| Field | Type | Required | Description |
| --- | --- | --- | --- |
| ride_id | string or null | no | Filter by ride id |
| event_types | array[string] or null | no | Filter by event type |

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
POST /api/v1/sse/rider/ack

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
| data | boolean or null | yes | Result flag |

### curl smoke test
```
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:7860/api/v1/sse/rider/stream?event_types=ride_status_update&ride_id=<ride_id>"
```

## Complete Rider Flow

1. **Authentication**: Rider signs up/logs in via REST API
2. **Open SSE Stream**: Rider connects to `/api/v1/sse/rider/stream`
3. **Setup Profile**: Rider updates profile and saves favorite addresses
4. **Request Ride**: Rider requests ride with pickup/destination
5. **Monitor Progress**: Rider receives real-time status updates via SSE
6. **Complete Ride**: Rider rates driver after ride completion
7. **View History**: Rider can view past rides and receipts

## Ride Request Flow

```javascript
// 1. Calculate fare estimate
const fareEstimate = await fetch('/api/v1/riders/place/calculate-fare', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({
    pickup: pickupPlaceId,
    destination: dropoffPlaceId,
    stops: []
  })
});

// 2. Request ride
const rideRequest = await fetch('/api/v1/riders/ride/request', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: JSON.stringify({
    pickup: pickupPlaceId,
    destination: dropoffPlaceId,
    vehicleType: 'CAR'
  })
});

// 3. Open SSE stream for ride updates
const streamResponse = await fetch(`/api/v1/sse/rider/stream?ride_id=${rideId}`, {
  headers: { 'Authorization': `Bearer ${token}` }
});
const reader = streamResponse.body.getReader();

// 4. Parse SSE events and acknowledge each one
// (Use your preferred SSE parsing utility or library.)
// When you receive an event with eventId, POST /api/v1/sse/rider/ack
```

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
- Monitor ride status via SSE for real-time updates
- Rate drivers promptly after ride completion

**Profile Management**
- Keep contact information up to date
- Save multiple addresses for convenience
- Use strong, unique passwords

**Payment**
- Verify payment methods before ride request
- Check receipts after ride completion
- Report payment issues immediately

**SSE Usage**
- Maintain a persistent stream during active rides
- Acknowledge events promptly to avoid retries
- Reconnect and resume stream on disconnects
