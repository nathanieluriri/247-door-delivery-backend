# Document Upload: Purpose and Flow

This document explains why driver document uploads exist, what they’re used for, and how the system handles them.

## Purpose
Driver document uploads are used to validate compliance and safety requirements before a driver can accept rides. The upload flow supports:
- Identity and vehicle compliance checks (e.g., license, registration, insurance).
- Background check workflows that depend on verified documents.
- Audit and review by admins, with a paper trail of what was submitted and when.
- Security controls (virus scanning, integrity checks, and quarantine of suspicious files).

## Where the documents are used
- **Driver onboarding & verification:** Documents are reviewed to approve or deny a driver.
- **Background checks:** Documents can trigger or unblock background verification.
- **Compliance audits:** Stored records help resolve disputes or regulatory reviews.

## Upload flow (high level)
1. Driver submits a file via `POST /api/v1/drivers/documents/upload` with a `documentType` and `file`.
2. The file is scanned for malware and quarantined if suspicious.
3. The file is stored using the configured storage backend (local or S3/R2).
4. A metadata record is saved in the database, including hash values for integrity verification.
5. Admins can review and approve/reject the document.

## documentType values
`documentType` is an enum and must be one of:
- `driver_license`
- `vehicle_registration`
- `insurance`
- `background_check`

## Re-upload rules
To prevent duplicate submissions:
- If a document of the same `documentType` is **pending** or **approved**, the upload endpoint returns the existing document instead of creating a new one.
- A driver can only re-upload after an admin **rejects** the previous document.

## Retrieval endpoints
- **Driver list:** `GET /api/v1/drivers/documents`  
  Returns all documents uploaded by the authenticated driver.
- **Admin pending by type:** `GET /api/v1/admins/driver-documents/pending?documentType=driver_license`  
  Returns pending documents grouped by driver ID (sorted newest-first on the backend).

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

## Notes
- The document upload is required for compliance; it is not intended for general file storage.
- If you need a general-purpose upload, use the dedicated Cloudflare upload endpoint.

## UI advice
- **Driver app:** show the last uploaded document per type with its status and “Uploaded at” time. If status is `pending` or `approved`, disable the upload button and show the review message.
- **Admin console:** group pending documents by driver, show the latest first, and provide one-click approve/reject with a reason field.
- **Status clarity:** always surface the status label (`pending`, `approved`, `rejected`) and the rejection reason if present.
