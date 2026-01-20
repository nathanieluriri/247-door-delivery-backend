# SSE Handler Documentation

This document describes the Server-Sent Events (SSE) streams for the Door Delivery Backend. SSE is one-way, server-to-client delivery for real-time updates such as ride requests, ride status changes, and chat messages. Actions remain REST-based.

## Authentication

All SSE endpoints require an `Authorization: Bearer <token>` header. Use a client that supports custom headers (mobile SDKs, server-side, or an EventSource polyfill).

## Stream Endpoints

- `GET /api/v1/sse/driver/stream`
- `GET /api/v1/sse/rider/stream`
- `GET /api/v1/chats/stream/{ride_id}` (chat-only convenience stream)
- `GET /api/v1/drivers/ride/{ride_id}/monitor` (driver-only ride stream)

### Optional Query Parameters

- `event_types`: repeatable filter, e.g. `event_types=ride_request&event_types=ride_status_update`
- `ride_id`: only emit events for a specific ride

## Event Format

Each SSE message contains:

```
id: <event_id>
event: <event_type>
data: {"id":"...","event":"...","data":{...},"createdAt":1700000000}
```

The JSON in `data` follows the `SSEEvent` schema:

```json
{
  "id": "event_id",
  "event": "ride_status_update",
  "data": {
    "rideId": "ride_id",
    "status": "arrivingToPickup",
    "message": "Ride status changed to arrivingToPickup",
    "etaMinutes": 5
  },
  "createdAt": 1700000000
}
```

## Event Types

### `ride_request`

```json
{
  "rideId": "ride_id",
  "pickup": "pickup_place_id_or_text",
  "destination": "destination_place_id_or_text",
  "vehicleType": "CAR",
  "fareEstimate": 1250,
  "riderId": "rider_id"
}
```

### `ride_status_update`

```json
{
  "rideId": "ride_id",
  "status": "drivingToDestination",
  "message": "Ride status changed to drivingToDestination",
  "etaMinutes": 12
}
```

### `chat_message`

```json
{
  "chatId": "chat_id",
  "rideId": "ride_id",
  "senderId": "user_id",
  "senderType": "RIDER",
  "message": "I'm at the pickup point",
  "timestamp": 1700000000
}
```

## Acknowledgements (Required)

Events must be acknowledged after processing. Unacknowledged events are re-sent after a short delay.

- `POST /api/v1/sse/driver/ack`
- `POST /api/v1/sse/rider/ack`

Payload:

```json
{
  "eventId": "event_id"
}
```

## Curl Smoke Tests

Stream driver events:

```
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:7860/api/v1/sse/driver/stream?event_types=ride_request"
```

Acknowledge an event:

```
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"eventId":"<event_id>"}' \
  "http://localhost:7860/api/v1/sse/driver/ack"
```
