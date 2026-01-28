# Finding Driver Flow (Detailed)

This file documents how the ride "findingDriver" flow behaves in the current app, including driver acceptance and no-driver outcomes, plus the admin/partner exceptions.

## 1) When Finding Driver Starts

Finding driver can begin in two ways:

1) **Normal rider request** (default flow)
   - A rider requests a ride using `POST /api/v1/riders/ride/request` (see `api/v1/rider_route.py`).
   - Ride is created with `rideStatus=pendingPayment`.
   - The system immediately publishes a `ride_request` SSE event to drivers.

2) **Admin-created ride** (payment not required to find driver)
   - An admin creates a ride using `POST /api/v1/admins/ride/{userId}`.
   - The ride is created with `rideStatus=findingDriver` and `paymentStatus=False`.
   - A payment link is generated (payment still required before completion), but driver discovery starts immediately.
   - The system publishes a `ride_request` SSE event to matching drivers.

3) **Partner rider** (payment not required to find driver)
   - If a rider has `title="partner"` (checked dynamically), the system sets:
     - `rideStatus=findingDriver`
     - `paymentStatus=False`
   - A payment link is generated (payment still required before completion), but driver discovery starts immediately.
   - The system publishes a `ride_request` SSE event to matching drivers.

## 2) Driver Discovery

- On ride creation, the backend calls `publish_ride_request(...)`.
- Drivers subscribed to SSE (`/api/v1/sse/driver/stream` or `/api/v1/drivers/ride/events`) receive `ride_request` events **only if**:
  - Their subscription is the active session for that driver, and
  - Their profile `vehicleType` matches the ride's `vehicleType`, and
  - Their live location (last updated via `POST /api/v1/drivers/location`) is within the discovery radius (default 5km).
- Each event contains `rideId`, pickup, destination, vehicleType, and fareEstimate (see `schemas/sse.py`).

## 3) Driver Accepts a Ride

When a driver accepts:

1) Driver calls: `POST /api/v1/drivers/ride/{ride_id}/accept`
2) Server updates the ride:
   - `driverId` is set to the driver’s ID
   - `rideStatus` is set to `arrivingToPickup`
3) SSE updates are emitted:
   - Rider receives `ride_status_update`
   - Driver receives `ride_status_update`

Next status transitions after acceptance:
1) `arrivingToPickup` → `drivingToDestination`
2) `drivingToDestination` → `completed`

These transitions are enforced by `ALLOWED_RIDE_STATUS_TRANSITIONS` in `schemas/imports.py`.

## 4) If No Driver Accepts

Two safeguards are used:

1) **Immediate availability check (rider flow)**
   - When a rider requests a ride, the system checks nearby drivers.
   - If no drivers are within 5km, the request is rejected immediately (`404`).

2) **Scheduled cleanup (findingDriver timeout)**
   - The ride service schedules a task after creation.
   - If the ride stays in `findingDriver` for ~5 minutes, it is deleted.
   - This is handled by:
     - `check_if_state_is_still_finding_driver_and_6_mins_have_passed_if_so_delete_the_ride`

## 5) Important Notes

- For **pendingPayment** rides, drivers can still receive the request event, but the ride is not paid yet.
- For **admin-created** and **partner** rides, payment is still required, but it is not required to start `findingDriver`.
- Refunds are only attempted if `paymentStatus=True` and a payment intent exists.
