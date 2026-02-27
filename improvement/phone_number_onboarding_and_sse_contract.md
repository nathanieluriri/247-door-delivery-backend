# Phone Number Onboarding and SSE UI Contract

## Summary
This document defines the new phone number behavior for drivers and riders, plus the SSE event contract the frontend should handle.

## Account Rules

## Driver (required)

Driver phone number is now required for operational onboarding.

Enforcement points:

- Driver profile completeness now includes `phoneNumber`.
- Driver SSE eligibility now fails if `phoneNumber` is missing.
- Driver location update is blocked if profile is incomplete (vehicle details + phone number).

Impact:

- A driver without phone number cannot complete operational onboarding flow.

## Rider (optional)

Rider phone number remains optional.

If missing, rider receives a non-blocking SSE prompt encouraging them to add it.

## Data Model Changes

## Driver

- `DriverCreate.phoneNumber?: string`
- `DriverUpdate.phoneNumber?: string`
- `DriverOut.phoneNumber?: string`
- New payload model: `DriverPhoneUpdate` (`phoneNumber: string`)

## Rider

- `RiderBase.phoneNumber?: string`
- `RiderUpdate.phoneNumber?: string`
- `RiderOut.phoneNumber?: string`
- New payload model: `RiderPhoneUpdate` (`phoneNumber: string`)

## Validation

Phone numbers are normalized with `strip()` and validated with:

- regex: `^[0-9+()\\- ]{7,20}$`

Invalid format returns request validation errors.

## New/Updated Endpoints

## Driver

### Update phone number

- Method: `PATCH`
- Path: `/api/v1/drivers/profile/phone`
- Auth: driver token required
- Body:

```json
{
  "phoneNumber": "+447123456789"
}
```

## Rider

### Update phone number

- Method: `PATCH`
- Path: `/api/v1/riders/profile/phone`
- Auth: rider token required
- Body:

```json
{
  "phoneNumber": "+447123456789"
}
```

## SSE Contract for Missing Rider Phone Number

When a rider opens SSE stream and phone number is missing, backend can emit:

- Event name: `profile_action_required`
- User type: `rider`
- Purpose: non-blocking profile completion hint

## Event type enum

`SSEEventType.profile_action_required = "profile_action_required"`

## Payload model

`ProfileActionRequiredEvent` fields:

- `actionType: string`
- `message: string`
- `field: string`
- `required: boolean` (for rider phone prompt this is `false`)
- `severity: string` (for rider phone prompt this is `"info"`)
- `ctaLabel?: string`
- `ctaPath?: string`

## Current phone prompt payload

```json
{
  "actionType": "add_phone_number",
  "message": "It would be nice to add your phone number for easier contact.",
  "field": "phoneNumber",
  "required": false,
  "severity": "info",
  "ctaLabel": "Add phone number",
  "ctaPath": "/profile/phone"
}
```

## UI Handling Guidance

Frontend should:

1. Listen for `profile_action_required` events on rider SSE stream.
2. For `actionType = "add_phone_number"`, show non-blocking prompt/banner/modal.
3. Use `ctaPath` to route to phone update screen/form.
4. Submit update with `PATCH /api/v1/riders/profile/phone`.
5. Dismiss prompt after successful update.

Notes:

- Prompt events are cooldown-throttled server-side via `PROFILE_ACTION_PROMPT_COOLDOWN_SECONDS` (default 86400 seconds).
- Event is informational; it must not block core rider flows.

