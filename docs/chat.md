# Chat Flow (Rider ↔ Driver)

This document explains how ride chat messages are **sent**, **broadcast**, and **received** using SSE, with concrete examples.

## 1) Send a message (create + broadcast)

**Endpoint**
- `POST /api/v1/chats`

**Auth**
- Required. Rider or Driver involved in the ride.
- Membership is enforced by `ensure_ride_membership` in `api/v1/chat.py`.

**Request body (ChatBase)**
- `rideId`: string
- `text`: string

**Server-side behavior (step-by-step)**
1. `verify_token` resolves the caller and returns `JWTPayload` with `user_type` and `user_id`.
2. `ensure_ride_membership` loads the ride and confirms:
   - If caller is a rider, `ride.userId == user.user_id`
   - If caller is a driver, `ride.driverId == user.user_id`
3. The API builds a `ChatCreate` payload with:
   - `rideId` and `text` from the request
   - `userType` and `userId` from the JWT
4. `services.chat_service.add_chat(...)`:
   - Creates a MongoDB record via `repositories.chat.create_chat`.
   - Publishes an SSE event (`chat_message`) via `services.sse_service.publish_chat_message`.
5. API returns `201` with the stored `ChatOut` record.

**Example: Rider sends a message**
```http
POST /api/v1/chats
Authorization: Bearer <rider_access_token>
Content-Type: application/json

{
  "rideId": "64f5d1a0b7c0a1e0f2d3c4b5",
  "text": "I'm at the pickup location."
}
```

**Example response**
```json
{
  "status_code": 201,
  "detail": "Message sent and broadcasted",
  "data": {
    "id": "66b0d7c2f0f1a3b12c345678",
    "rideId": "64f5d1a0b7c0a1e0f2d3c4b5",
    "text": "I'm at the pickup location.",
    "dateCreated": 1760000000,
    "lastUpdated": 1760000000
  }
}
```

## 2) Receive real-time messages (SSE)

**Endpoint**
- `GET /api/v1/chats/stream/{ride_id}`

**Auth**
- Required. Rider or Driver involved in the ride.
- Membership is enforced by `ensure_ride_membership` before stream starts.

**SSE filters used internally**
- `event_types=["chat_message"]`
- `ride_id={ride_id}`

**What happens when you connect (step-by-step)**
1. The server verifies the token and ride membership.
2. The SSE stream is opened via `services.sse_service.stream_events`.
3. The stream reads pending SSE events from Redis and filters by:
   - `event_type == "chat_message"`
   - `ride_id` matches the requested ride
4. When a chat message is sent, both the rider and driver receive the same `chat_message` event.

**Event payload (chat_message)**
- `chatId`: string
- `rideId`: string
- `senderId`: string
- `senderType`: `rider` | `driver` | `admin`
- `message`: string
- `timestamp`: unix timestamp (seconds)

**Example: Open SSE stream**
```http
GET /api/v1/chats/stream/64f5d1a0b7c0a1e0f2d3c4b5
Authorization: Bearer <driver_or_rider_access_token>
Accept: text/event-stream
```

**Example: SSE event received**
```text
id: 4caa5f7b9e7843e6a8f1b3c2d4e5f6a7
event: chat_message
data: {"id":"4caa5f7b9e7843e6a8f1b3c2d4e5f6a7","event":"chat_message","data":{"chatId":"66b0d7c2f0f1a3b12c345678","rideId":"64f5d1a0b7c0a1e0f2d3c4b5","senderId":"driver_123","senderType":"driver","message":"I'm 2 minutes away.","timestamp":1760000020},"createdAt":1760000020}
```

**Notes**
- Keep the SSE connection open; the server sends keep-alive comments if idle.
- Only the ride’s rider and assigned driver will receive these events.

## 3) Get chat history for a ride

**Endpoint**
- `GET /api/v1/chats/{rideId}`

**Auth**
- Not enforced in current code (public). Consider adding membership checks if needed.

**Example**
```http
GET /api/v1/chats/64f5d1a0b7c0a1e0f2d3c4b5
```

## 4) Delete a message

**Endpoint**
- `DELETE /api/v1/chats/{id}`

**Auth**
- Not enforced in current code (public). Consider restricting.

**Example**
```http
DELETE /api/v1/chats/66b0d7c2f0f1a3b12c345678
```

## Data models

**ChatBase**
- `rideId`, `text`

**ChatOut**
- `id`
- `rideId`, `text`
- `dateCreated`, `lastUpdated`

## Key files
- `api/v1/chat.py`
- `services/chat_service.py`
- `services/sse_service.py`
- `schemas/chat.py`
- `schemas/sse.py`
