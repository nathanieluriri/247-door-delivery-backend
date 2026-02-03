# Background Checks

## Flow
1) Admin or system creates a background check record on driver signup (already auto-created).
2) Provider ingestion endpoint updates status to PASSED/FAILED with reference and notes.
3) If all required documents (license, registration, insurance) are approved and background is PENDING, system auto-passes and logs audit.
4) Driver activation remains gated: accountStatus cannot become ACTIVE unless background status is PASSED.

## Admin API
- List: `GET /api/v1/admins/background-checks`
- Update: `PATCH /api/v1/admins/driver/{driverId}/background` body `{ "status": "passed|failed", "notes": "...", "referenceId": "..." }`

## Provider Ingestion (to add)
- Endpoint stub: `POST /api/v1/admins/driver/{driverId}/background/provider` with provider payload → map to status, notes, reference; logs audit.

## Auto-linking
- When a document is approved, system attempts auto-pass if all required docs are approved and background is still PENDING.

## Required documents for auto-pass
- driver_license
- vehicle_registration
- insurance

## Audit
- All background updates and auto-pass events are written to audit log (actor=admin or system).
