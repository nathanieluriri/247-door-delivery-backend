# Booking Flow and Timeout Improvement Plan

## Why this plan exists
Current ride creation + payment + timeout handling has three product risks:
1. Rider may pay before any driver is confirmed.
2. Final trip cost can exceed estimated fare, but there is no explicit settlement strategy for the difference.
3. Timeout jobs delete rides, which removes audit/history and can leave frontend flows inconsistent.

This plan proposes a staged redesign that preserves reliability and keeps full ride history.

## Current behavior (from code)

- Ride request creation currently creates a payment link and publishes a driver request in the same flow.
  - `services/ride_service.py` (`add_ride`)
- Payment confirmation webhook pushes ride to `findingDriver`.
  - `core/payments.py` (`checkout.session.completed` -> `RideStatus.findingDriver`)
- Two scheduler jobs can delete rides if they stay in timeout states:
  - `check_if_state_is_still_pending_payment_and_delete_ride_if_it_is_still_pending_payment`
  - `check_if_state_is_still_finding_driver_and_6_mins_have_passed_if_so_delete_the_ride`
  - both call Celery task `delete_ride`.
- Async task registry includes hard delete for rides.
  - `core/tasks.py` (`"delete_ride": remove_ride`)

## Target outcomes

1. No rider is charged before a driver is actually available/assigned.
2. Final fare settlement is explicit and handles overages safely.
3. Timeout handling never hard-deletes rides; it transitions state with reason metadata.
4. Frontend receives deterministic terminal states (`canceled`/`stale`) instead of missing rides.

## Proposed booking/payment lifecycle

## Phase A (recommended first): Match-first, then payment authorization

1. Rider submits booking request.
2. Backend creates ride in `findingDriver` with `paymentStatus=false` and estimated fare.
3. Driver is matched and accepts.
4. Ride transitions to payment gate state, then rider pays/authorizes.
5. On payment success, ride moves to `arrivingToPickup`.
6. If payment times out after match, ride becomes system-canceled with reason.

Implementation option for the payment gate state:
- Minimal-change option: reuse `pendingPayment` but only after driver accept.
- Cleaner option: add new status `awaitingPaymentAuthorization`.

## Phase B: Final settlement for estimate vs actual

At ride completion:
1. Compute final fare from actual duration/distance.
2. Compare with authorized/paid amount.
3. Apply one of:
- capture authorized amount if sufficient
- incremental authorization or post-trip invoice for positive balance
- partial refund for over-collection

Recommended payment mechanism shift:
- Move from pure Payment Link flow to PaymentIntent-based authorization/capture for better final-fare control.

## Timeout behavior redesign (replace delete with state transitions)

## Rules

- `pendingPayment` timeout -> `canceled` with reason `payment_timeout_unpaid`.
- `findingDriver` timeout (current 6-minute path) -> `canceled` with reason `no_driver_found_timeout`.
- Optional future status: `stale` for recoverable/system-stuck states.

## Metadata to persist on timeout transition

- `closeReason` (enum/string)
- `closedBy` = `system`
- `closedAt` (unix time)
- `timeoutSeconds` (for observability)

## Important

Do not hard-delete rides in automated timeout paths.

## Data model updates

## Ride status / reason model

- Keep `RideStatus` terminal state as `canceled` for compatibility.
- Add `RideCloseReason` enum, e.g.:
  - `no_driver_found_timeout`
  - `payment_timeout_unpaid`
  - `rider_canceled`
  - `driver_canceled`
  - `admin_canceled`
  - `system_stale_cleanup`

## Ride schema additions

- `closeReason: Optional[str]`
- `closedBy: Optional[str]`
- `closedAt: Optional[int]`
- `estimatedPrice: Optional[float]`
- `finalPrice: Optional[float]`
- `fareDelta: Optional[float]`

## Backend implementation plan (file-level)

1. `services/ride_service.py`
- Replace both delete-timeout functions with expire/cancel functions.
- Add a single helper: `expire_ride_due_to_timeout(ride_id, reason)`.
- Ensure timeout transition emits SSE and clears dispatch scheduler job.

2. `core/tasks.py`
- Add `expire_ride` task (or reuse `update_ride` with system payload).
- Keep `delete_ride` only for explicit admin/manual purge, not scheduler timeout flow.

3. `schemas/imports.py` and `schemas/ride.py`
- Add cancellation reason fields (and optional new payment-gate status if chosen).
- Update transition map if new status is introduced.

4. `repositories/ride.py`
- Update active-ride filter logic to include/exclude new states correctly.
- Ensure canceled-by-timeout rides are not treated as active.

5. `core/payments.py`
- Move payment trigger to post-match stage.
- Add final-fare settlement path on completion.

6. `api/v1/driver.py` and rider booking endpoints
- Align accept/start transitions with the new payment gate behavior.

## Frontend impact

- Rider app must handle new cancellation reasons and show actionable messages:
  - "No drivers found"
  - "Payment window expired"
- Booking screen should not require immediate payment before match.
- Ride history should include timed-out rides (canceled with reason), not disappear.

## Migration strategy

1. Deploy schema fields first (backward compatible).
2. Switch scheduler jobs from delete to cancel-reason transitions.
3. Backfill currently stuck old rides:
- if `findingDriver` older than timeout -> cancel with `no_driver_found_timeout`
- if `pendingPayment` unpaid and expired -> cancel with `payment_timeout_unpaid`
4. Then roll out payment lifecycle change (match-first payment).

## Testing plan

1. Unit tests
- Timeout jobs never call hard delete.
- Timeout transitions set status + reason + timestamps.
- Transition validation still enforced.

2. Integration tests
- No-driver timeout ends in `canceled` + reason.
- Payment-timeout-after-match ends in `canceled` + reason.
- History endpoint still returns timed-out rides.

3. Payment tests
- Estimated vs final fare settlement for:
  - exact fare
  - higher final fare
  - lower final fare

## Acceptance criteria

- Automated timeout path performs state transition, not deletion.
- Riders can see timed-out rides in history with explicit reason.
- No pre-match mandatory charge in the default booking path.
- Final-fare settlement path exists for over/under estimate outcomes.
- SSE updates are emitted for system timeout cancellations.

## Proposed execution order

1. Timeout deletion -> cancellation reason transition.
2. Cancellation metadata + frontend reason rendering.
3. Match-first payment flow.
4. Final fare settlement enhancements.
