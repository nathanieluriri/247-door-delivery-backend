# Admin Frontend Flow (Integration Guide)

Use `base_url` as the environment-specific API origin. All endpoints below are shown as `base_url/endpoint`.

## 1) Authentication and Session

- Sign up (admin-only, requires admin token): `POST base_url/api/v1/admins/signup`
- Log in: `POST base_url/api/v1/admins/login`
- Refresh token: `POST base_url/api/v1/admins/refresh` (send expired access token in `Authorization: Bearer <token>` and refresh token in body)

Store `accessToken` and `refreshToken` from auth responses. Use `Authorization: Bearer <accessToken>` for all protected routes.

## 2) Admin Profile and Account

- List admins: `GET base_url/api/v1/admins?start=0&stop=100`
- Get current admin profile: `GET base_url/api/v1/admins/profile`
- Update profile: `PATCH base_url/api/v1/admins/profile`
- Delete admin account: `DELETE base_url/api/v1/admins/account`

## 3) Driver Management

- List drivers: `GET base_url/api/v1/admins/drivers?start=0&stop=100`
- Get driver: `GET base_url/api/v1/admins/driver/{driverId}`
- Ban driver: `PATCH base_url/api/v1/admins/ban/driver/{driverId}`
- Approve driver: `PATCH base_url/api/v1/admins/approve/driver/{driverId}`

## 4) Rider Management

- List riders: `GET base_url/api/v1/admins/riders?start=0&stop=100`
- Get rider: `GET base_url/api/v1/admins/rider/{riderId}`
- Ban rider: `PATCH base_url/api/v1/admins/ban/rider/{riderId}`
- Search riders (email/status): `GET base_url/api/v1/admins/riders/search?email_address=<email>&status=<status>&start=0&stop=100`
  - Returns `UserOut[]` for autocomplete/filters.

## 5) User Search (Autocomplete)

- Search users by email or id: `GET base_url/api/v1/admins/users/search?q=<email_or_id>&limit=10`
  - Searches riders and drivers by email (case-insensitive, partial match).
  - If `q` is a valid ObjectId, returns exact id match too.
  - Returns `UserOut[]` with `userType`.

## 6) Ride Management

- Create ride for user: `POST base_url/api/v1/admins/ride/{userId}`
- Get rides by rider: `GET base_url/api/v1/admins/ride/{riderId}`
- Get rides by driver: `GET base_url/api/v1/admins/ride/{driverId}`
- Cancel ride: `PATCH base_url/api/v1/admins/ride/{rideId}` with body `{"rideStatus": "canceled"}`

## 7) Invoice Management

- Generate invoice: `POST base_url/api/v1/admins/invoice/{rideId}`
- Get invoice: `GET base_url/api/v1/admins/invoice/{rideId}`

## 8) Password Management

- Change password (logged in): `PATCH base_url/api/v1/admins/password-reset`
- Request password reset: `POST base_url/api/v1/admins/password-reset/request`
- Confirm password reset: `PATCH base_url/api/v1/admins/password-reset/confirm`

## 9) Permissions and Audit

- All admin routes require a valid admin token and pass `check_admin_account_status_and_permissions`.
- Actions are logged via `log_what_admin_does` for auditability.

## 10) Schemas (Requests/Responses)

Schema sources are in `schemas/*.py`. Commonly used fields:

- Admin: `AdminBase` (full_name, email, password, permissionList), `AdminCreate` (+invited_by), `AdminLogin` (email, password), `AdminRefresh` (refreshToken), `AdminUpdate` (full_name), `AdminUpdatePassword` (password), `AdminOut` (id, fullName, email, accountStatus, permissionList, invitedBy, accessToken?, refreshToken?, dateCreated, lastUpdated)
- User search: `UserOut` (id, email, firstName?, lastName?, fullName?, accountStatus?, userType)
- Drivers: `DriverOut` (id, email, firstName, lastName, accountStatus, stripeAccountId?, accessToken?, refreshToken?, dateCreated, lastUpdated), `DriverUpdateAccountStatus` (accountStatus)
- Riders: `RiderOut` (id, email, firstName, lastName, accountStatus, accessToken?, refreshToken?, dateCreated, lastUpdated), `RiderUpdateAccountStatus` (accountStatus)
- Rides: `RideBase` (pickup, destination, vehicleType, stops?), `RideUpdate` (rideStatus, driverId?), `RideOut` (id, pickup, destination, vehicleType, rideStatus, driverId?, userId, price?, paymentStatus, paymentLink?, origin?, map?, dateCreated, lastUpdated)
- Invoices/Payments: `InvoiceData` (id, status?, amount_paid, currency?, customer?, emailSentTo?, invoiceUrl?, metadata)
- Password reset: `ResetPasswordInitiation` (email), `ResetPasswordInitiationResponse` (resetToken), `ResetPasswordConclusion` (otp, resetToken, password)
- Permissions: `PermissionList` (permissions[]), `Permission` (name, methods[], path, description?)

Key enums used in admin flows: `AccountStatus`, `RideStatus`, `VehicleType`, `LoginType`, `PermissionList`.

## 11) Response Wrapper

Most endpoints return `APIResponse`:
```
{
  "status_code": 200,
  "detail": "Message",
  "data": { ... }
}
```
