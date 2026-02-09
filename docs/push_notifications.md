# Push Notifications

This document explains how push notifications are registered and when they are sent.

## 1) Register a push token (driver)

**Endpoint**
- `POST /api/v1/drivers/push/register`

**Auth**
- Driver token required
- Account must be active

**Body**
- `playerId`: string (OneSignal player/device ID)

**Example**
```http
POST /api/v1/drivers/push/register
Authorization: Bearer <driver_access_token>
Content-Type: application/json

{
  "playerId": "onesignal_player_id_123"
}
```

**Response**
- `data`: list of registered player IDs for this driver

## 2) Register a push token (rider)

**Endpoint**
- `POST /api/v1/riders/push/register`

**Auth**
- Rider token required
- Account must be active

**Body**
- `playerId`: string (OneSignal player/device ID)

**Example**
```http
POST /api/v1/riders/push/register
Authorization: Bearer <rider_access_token>
Content-Type: application/json

{
  "playerId": "onesignal_player_id_456"
}
```

**Response**
- `data`: list of registered player IDs for this rider

## 3) When push notifications are sent

Push notifications are sent asynchronously for the following events:

1. **Ride request**
- Recipient: Driver
- Trigger: New ride request broadcast
- Title: `New ride request`
- Body: `{pickup} → {destination}`

2. **Ride status update**
- Recipients: Rider and Driver
- Trigger: Ride status transitions
- Title: `Ride status update`
- Body: `Ride {rideId} status changed to {status}`

3. **Chat message**
- Recipient: The other party (not the sender)
- Trigger: New chat message
- Title: `New message from rider` or `New message from driver`
- Body: `{message}`

## 4) Check push status

### Driver

**Endpoint**
- `GET /api/v1/drivers/push/status`

**Auth**
- Driver token required

**Response**
- `data.enabled`: `true` if any player IDs are registered

### Rider

**Endpoint**
- `GET /api/v1/riders/push/status`

**Auth**
- Rider token required

**Response**
- `data.enabled`: `true` if any player IDs are registered

## 5) Fallback behavior

If push cannot be delivered:
- The system attempts SMS (currently stubbed).
- Then attempts email (if SMTP configured).
- If all fail, the notification is enqueued for retry or DLQ.

## 6) Storage

Registered OneSignal player IDs are stored in Redis:
- Key format: `push:player_ids:{user_type}:{user_id}`
- TTL is configurable via `PUSH_TOKEN_TTL_SECONDS` (default 30 days).

## 7) Required environment variables

Push (OneSignal) requires:
- `ONESIGNAL_APP_ID`
- `ONESIGNAL_API_KEY`

Email fallback requires:
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USERNAME`
- `EMAIL_PASSWORD`
- `EMAIL_USE_TLS`

## Key files
- `services/notification_service.py`
- `services/push_notification.py`
- `services/notification_targets.py`
- `api/v1/driver.py`
- `api/v1/rider_route.py`
