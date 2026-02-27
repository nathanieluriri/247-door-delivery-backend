# Post-Ride Rating Frontend UI Guide

## Goal
Make post-ride rating mandatory in UI for both rider and driver, based on backend `ratingStatus`.

Use this with:
- `docs/post_ride_rating_contract.md`

Backend is the source of truth. Frontend must never unlock core operations using local assumptions only.

## Source of Truth
Read `ratingStatus` from ride payloads and SSE ride updates:

```json
{
  "ratingStatus": {
    "riderMustRate": true,
    "driverMustRate": true,
    "riderRated": false,
    "driverRated": false,
    "riderRatedAt": null,
    "driverRatedAt": null
  }
}
```

Gate conditions:
- Rider pending: `riderMustRate && !riderRated`
- Driver pending: `driverMustRate && !driverRated`

## UX Principles
- No skip for mandatory rating.
- Clear reason for lock.
- Clear route to fix lock (open rating screen for blocking ride).
- Preserve access to non-core screens.
- Persist lock across app restart and device switch via backend refresh.

## Allowed vs Blocked Actions
### Rider
Blocked while pending:
- New ride request flow.
- Any CTA that starts fare estimate -> request ride.

Allowed while pending:
- Profile.
- Support/help.
- Ride history.
- Ride details.
- Logout.
- Rating submission.

### Driver
Blocked while pending:
- Go online / stream start.
- Location updates used for active operations.
- Accept ride.
- Start ride.
- Complete ride.

Allowed while pending:
- Profile.
- Support/help.
- Ride history.
- Ride details.
- Logout.
- Rating submission.

## Required App States
Use explicit lock state instead of overloading unrelated states.

Recommended:
- `NORMAL`
- `RATING_REQUIRED`

Store lock state with:
- `pendingRideId`
- `userType` (`rider` or `driver`)
- `ratingStatus`
- `lastSyncedAt`

## Entry Points to Evaluate Lock
Evaluate lock in all of the following:
- App launch.
- Login success.
- Pull-to-refresh on home/dashboard.
- Receiving ride-related SSE events.
- Returning from background.
- After rating submit success.

## Screen-Level Instructions
### Rider Home / Request Ride Entry
- If pending, disable request CTAs.
- Show fixed inline banner at top:
  - Title: `Rating required`
  - Body: `Rate your last ride to continue booking.`
  - CTA: `Rate now`
- CTA opens rating screen for `pendingRideId`.

### Driver Home / Go Online
- If pending, disable online toggle and operation buttons.
- Replace primary action area with blocking card:
  - Title: `Rating required`
  - Body: `Rate your last rider to continue driver operations.`
  - CTA: `Rate now`

### Mandatory Rating Screen
- Must be non-dismissable while pending.
- Hide close icon.
- Disable back navigation if it leads to blocked operation path.
- Show ride summary:
  - Ride ID.
  - Counterparty name.
  - Date/time.
  - Pickup/destination summary.
- Rating controls:
  - 1-5 star selector.
  - Optional comment field only if backend supports it.
  - Submit button.
- Submission states:
  - Idle.
  - Submitting.
  - Failed (retry available).
  - Success (then refresh lock state from backend).

## History and Ride Details UI
Show rating status badges per ride:
- `Rating pending` when current user still must rate.
- `Rated` when current user already rated.

Badge placement:
- Ride history card trailing area.
- Ride details header under status.

## Navigation Guard Rules
- If route is blocked and lock is active, redirect to rating screen.
- If route is allowed, do not force redirect.
- Keep guard logic centralized:
  - `canAccessRoute(route, lockState)`
  - `canExecuteAction(action, lockState)`

## API and Error Handling
### Rating Submit
- On success:
  - Immediately fetch ride details for same `rideId`.
  - Recompute lock from returned `ratingStatus`.
  - Unlock only when backend confirms current user rated.

### If submit fails
- Keep lock active.
- Show retryable error toast and inline error on screen.

### If blocked endpoint returns 403
Expected examples:
- `detail.code = RATING_REQUIRED_RIDER`
- `detail.code = RATING_REQUIRED_DRIVER`

Behavior:
- Parse `detail.rideId`.
- Update lock state with this ride.
- Redirect to mandatory rating screen.

### If `ratingStatus` is missing unexpectedly
- Fail safe.
- Keep lock active if there is known pending ride from previous state or 403 gate code.
- Trigger immediate refetch of latest ride history/details.

## Realtime Sync
- When SSE `ride_status_update` includes `ratingStatus`, update lock state immediately.
- Do not wait for manual refresh.
- If SSE disconnects, fallback to periodic pull on foreground resume.

## Copy Guidelines
Rider:
- Title: `Rate your driver`
- Body: `You need to rate this ride before requesting another one.`
- Button: `Submit rating`

Driver:
- Title: `Rate your rider`
- Body: `You need to rate this ride before continuing driver operations.`
- Button: `Submit rating`

Error:
- `Couldn't submit rating. Please try again.`

## Accessibility
- Star inputs must be keyboard and screen-reader accessible.
- Provide text equivalent for selected rating:
  - `3 out of 5 stars selected`.
- Ensure disabled buttons include reason text nearby.
- Keep color contrast of `Rating pending` badge WCAG-compliant.

## Telemetry
Track these events:
- `rating_gate_shown`
- `rating_gate_blocked_action`
- `rating_submit_attempt`
- `rating_submit_success`
- `rating_submit_failure`
- `rating_gate_cleared`

Include:
- `userType`
- `rideId`
- `entryPoint` (home, request_button, online_toggle, deep_link, etc)

## QA Checklist
- Rider with pending rating cannot request a new ride.
- Rider can still open profile/support/history/details/logout.
- Driver with pending rating cannot go online/accept/start/complete/update location.
- Driver can still open profile/support/history/details/logout.
- Rating screen cannot be skipped while pending.
- Successful submit unlocks only after backend confirmation.
- Restart app keeps lock until backend confirms rated.
- Ride history and details correctly show `Rating pending`.

## Implementation Order
1. Build lock-state store and helpers.
2. Add route/action guards.
3. Build mandatory rating screen UX.
4. Wire API submit + post-submit refresh.
5. Add history/details badges.
6. Add telemetry.
7. Execute QA checklist.
