# Document Upload: Purpose, Rules, and Admin Review

This document explains why driver document uploads exist, how they are used, and how admins review them.

## Purpose
Driver document uploads are used to validate compliance and safety requirements before a driver can accept rides. The upload flow supports:
- Identity and vehicle compliance checks (license, registration, insurance).
- Background check workflows that depend on verified documents.
- Audit and review by admins with a clear paper trail.
- Security controls (virus scanning, integrity checks, and quarantine of suspicious files).

## documentType values
`documentType` is an enum and must be one of:
- `driver_license`
- `vehicle_registration`
- `insurance`
- `background_check`

## Upload flow (high level)
1. Driver submits a file via `POST /api/v1/drivers/documents/upload` with a `documentType` and `file`.
2. The file is scanned for malware and quarantined if suspicious.
3. The file is stored using the configured storage backend (local or S3/R2).
4. A metadata record is saved in the database, including hash values for integrity verification.
5. Admins can review and approve/reject the document.

## Re-upload rules
To prevent duplicate submissions:
- If a document of the same `documentType` is **pending** or **approved**, the upload endpoint returns the existing document instead of creating a new one.
- A driver can only re-upload after an admin **rejects** the previous document.

## Retrieval endpoints
### Driver: list all documents
- `GET /api/v1/drivers/documents`

### Driver: latest document per type
- `GET /api/v1/drivers/documents/latest`

Returns the most recent document for each `documentType` for the authenticated driver.

### Admin: pending docs by type (grouped by driver)
- `GET /api/v1/admins/driver-documents/pending?documentType=driver_license`

Optional filters:
- `driverId=<driver_id>` limits results to a single driver.
- `sortBy=uploadedAt` (only allowed sort field)
- `sortDir=asc|desc`

Backend sorting is applied; clients should not pass arbitrary sort fields.

## Admin approval and rejection
The admin review endpoint supports both **approve** and **reject** actions by passing the desired status.

### Approve endpoint
- **Method + URL:** `PATCH /api/v1/admins/driver/{driverId}/documents/{docId}`
- **Payload:**
```json
{ "status": "approved" }
```
- **Response:**
```json
{
  "status_code": 200,
  "data": { "document": { "id": "doc_id", "status": "approved" } },
  "detail": "Document status updated"
}
```

### Reject endpoint
- **Method + URL:** `PATCH /api/v1/admins/driver/{driverId}/documents/{docId}`
- **Payload:**
```json
{ "status": "rejected", "reason": "Blurry photo" }
```
- **Response:**
```json
{
  "status_code": 200,
  "data": { "document": { "id": "doc_id", "status": "rejected", "reason": "Blurry photo" } },
  "detail": "Document status updated"
}
```

### Required fields
- `driverId` (path): driver owning the document
- `docId` (path): document ID to review
- `status` (body): `approved` or `rejected`
- `reason` (body): required when `status` is `rejected`
- `adminId`: derived from the admin auth token (not sent in payload)

## Example responses
### Upload blocked (pending/approved exists)
```json
{
  "status_code": 200,
  "data": {
    "id": "doc_id",
    "driverId": "driver_id",
    "documentType": "driver_license",
    "status": "pending"
  },
  "detail": "Document already uploaded; pending or approved documents must be reviewed before re-upload."
}
```

### Driver latest documents
```json
{
  "status_code": 200,
  "data": [
    { "documentType": "driver_license", "status": "approved" },
    { "documentType": "insurance", "status": "pending" }
  ],
  "detail": "Latest documents fetched"
}
```

### Admin pending list by type
```json
{
  "status_code": 200,
  "data": [
    {
      "driverId": "driver_id",
      "documents": [
        { "id": "doc_id", "documentType": "driver_license", "status": "pending" }
      ]
    }
  ],
  "detail": "Pending documents fetched"
}
```

## Security controls
- **Virus scanning:** Uploads are scanned; infected files are quarantined.
- **Integrity hashing:** SHA-256 and MD5 hashes are stored to verify file integrity.
- **Quarantine workflow:** Suspicious files are stored separately for admin review.
- **Signed URLs (S3/R2):** Optional presigned URLs are used for secure access without exposing raw storage credentials.

## UI advice
- **Driver app:** show the last uploaded document per type with its status and “Uploaded at” time. If status is `pending` or `approved`, disable the upload button and show the review message.
- **Admin console:** group pending documents by driver, show the latest first, and provide one-click approve/reject with a reason field.
- **Status clarity:** always surface the status label (`pending`, `approved`, `rejected`) and the rejection reason if present.

## Notes
- The document upload is required for compliance; it is not intended for general file storage.
- If you need a general-purpose upload, use the dedicated Cloudflare upload endpoint.
