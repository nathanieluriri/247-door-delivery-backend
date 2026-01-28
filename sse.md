# SSE API Documentation

This document describes all Server-Sent Events (SSE) endpoints, payloads, and acknowledgement behavior.

## Overview

SSE provides one-way, server-to-client delivery for real-time updates. All actions (ride creation, accept, cancel, payments, chat send) remain REST-based.

## Authentication

All SSE endpoints require:

- `Authorization: Bearer <access_token>`

Use a client that supports custom headers (mobile SDKs, server-side, or an EventSource polyfill).

## Common Event Envelope

Each SSE message contains:

```
id: <event_id>
event: <event_type>
data: {"id":"...","event":"...","data":{...},"createdAt":1700000000}
```

Envelope fields:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| id | string | yes | SSE event id |
| event | string | yes | SSE event name |
| data.id | string | yes | Event id |
| data.event | string | yes | Event name |
| data.data | object | yes | Event payload |
| data.createdAt | integer | yes | Unix timestamp |

## Event Types and Payloads

### ride_request

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| rideId | string | yes | Ride id |
| pickup | string | yes | Pickup place id or label |
| destination | string | yes | Destination place id or label |
| vehicleType | string | yes | Vehicle type (for example: CAR, MOTOR_BIKE) |
| fareEstimate | number or null | no | Fare estimate |
| riderId | string or null | no | Rider id |

### ride_status_update

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| rideId | string | yes | Ride id |
| status | string | yes | pendingPayment, findingDriver, arrivingToPickup, drivingToDestination, canceled, completed |
| message | string or null | no | Status message |
| etaMinutes | integer or null | no | ETA in minutes |

### chat_message

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| chatId | string | yes | Chat id |
| rideId | string | yes | Ride id |
| senderId | string | yes | Sender id |
| senderType | string | yes | RIDER or DRIVER |
| message | string | yes | Message body |
| timestamp | integer | yes | Unix timestamp |

## Endpoints

The core SSE endpoints live under `/api/v1/sse/*`. Additional SSE streams are defined in the driver and chat routers.

## Core SSE Endpoints

### Driver SSE stream

```
GET /api/v1/sse/driver/stream
Authorization: Bearer <access_token>
```

Query parameters:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| ride_id | string or null | no | Filter by ride id |
| event_types | array[string] or null | no | Filter by event type |

Notes:
- Only the latest active driver subscription receives `ride_request` events.
- Driver `ride_request` events are filtered by driver vehicle type and live location.
- Drivers update live location via `POST /api/v1/drivers/location`.
- Vehicle details are set via `PUT /api/v1/drivers/vehicle`.
- Drivers with incomplete vehicle details do not receive `ride_request` events.

Response example (SSE):
```
HTTP/1.1 200 OK
Content-Type: text/event-stream

id: e7b0f4b2e0b54d1e9f1c2f2d8b8a1111
event: ride_request
data: {"id":"e7b0f4b2e0b54d1e9f1c2f2d8b8a1111","event":"ride_request","data":{"rideId":"ride_123","pickup":"place_pickup_id","destination":"place_destination_id","vehicleType":"CAR","fareEstimate":12.5,"riderId":"rider_456"},"createdAt":1700000000}
```

### Rider SSE stream

```
GET /api/v1/sse/rider/stream
Authorization: Bearer <access_token>
```

Query parameters:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| ride_id | string or null | no | Filter by ride id |
| event_types | array[string] or null | no | Filter by event type |

Response example (SSE):
```
HTTP/1.1 200 OK
Content-Type: text/event-stream

id: a3c9f2d1b7e94f2f8a1c9b2f11112222
event: ride_status_update
data: {"id":"a3c9f2d1b7e94f2f8a1c9b2f11112222","event":"ride_status_update","data":{"rideId":"ride_123","status":"arrivingToPickup","message":"Driver is on the way","etaMinutes":5},"createdAt":1700000000}
```

### Driver ack

```
POST /api/v1/sse/driver/ack
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "eventId": "event_id"
}
```

Response body:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data | boolean or null | yes | Acknowledgement result |

Response example:
```json
{
  "status_code": 200,
  "detail": "Event acknowledged",
  "data": true
}
```

### Rider ack

```
POST /api/v1/sse/rider/ack
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "eventId": "event_id"
}
```

Response body:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| status_code | integer | yes | HTTP status code |
| detail | string | yes | Message |
| data | boolean or null | yes | Acknowledgement result |

Response example:
```json
{
  "status_code": 200,
  "detail": "Event acknowledged",
  "data": true
}
```

## Additional SSE Streams

### Driver ride events stream

```
GET /api/v1/drivers/ride/events
Authorization: Bearer <access_token>
```

Notes:
- Streams ride_request and ride_status_update events for the driver.
- `ride_request` events are filtered by vehicle type and distance to pickup.

Response example (SSE):
```
HTTP/1.1 200 OK
Content-Type: text/event-stream

id: f4f1e98d7a1b4c99a111222233334444
event: ride_request
data: {"id":"f4f1e98d7a1b4c99a111222233334444","event":"ride_request","data":{"rideId":"ride_456","pickup":"place_pickup_id","destination":"place_destination_id","vehicleType":"CAR","fareEstimate":9.8,"riderId":"rider_789"},"createdAt":1700000000}
```

### Driver ride monitor stream

```
GET /api/v1/drivers/ride/{ride_id}/monitor
Authorization: Bearer <access_token>
```

Notes:
- Streams ride_status_update and chat_message events for the specified ride.

Response example (SSE):
```
HTTP/1.1 200 OK
Content-Type: text/event-stream

id: c9b6d6e0a2b54f4c9a9f555566667777
event: chat_message
data: {"id":"c9b6d6e0a2b54f4c9a9f555566667777","event":"chat_message","data":{"chatId":"chat_123","rideId":"ride_123","senderId":"driver_123","senderType":"DRIVER","message":"Arriving now","timestamp":1700000000},"createdAt":1700000000}
```

### Ride chat stream

```
GET /api/v1/chats/stream/{ride_id}
Authorization: Bearer <access_token>
```

Notes:
- Streams chat_message events for the specified ride.

Response example (SSE):
```
HTTP/1.1 200 OK
Content-Type: text/event-stream

id: d1c2b3a4e5f647889999aaaabbbbcccc
event: chat_message
data: {"id":"d1c2b3a4e5f647889999aaaabbbbcccc","event":"chat_message","data":{"chatId":"chat_456","rideId":"ride_456","senderId":"rider_456","senderType":"RIDER","message":"I'm at the pickup point","timestamp":1700000000},"createdAt":1700000000}
```

## Acknowledgements (Required)

Events must be acknowledged after processing. Unacknowledged events are re-sent after a short delay.

## Curl Smoke Tests

Driver stream:

```
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:7860/api/v1/sse/driver/stream?event_types=ride_request"
```

Rider stream:

```
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:7860/api/v1/sse/rider/stream?event_types=ride_status_update&ride_id=<ride_id>"
```

Ack driver event:

```
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"eventId":"<event_id>"}' \
  "http://localhost:7860/api/v1/sse/driver/ack"
```

Ack rider event:

```
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"eventId":"<event_id>"}' \
  "http://localhost:7860/api/v1/sse/rider/ack"
```
