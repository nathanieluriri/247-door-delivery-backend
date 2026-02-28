# Driver Headshot Upload + Admin Approval Contract

## Purpose
This backend already supports driver headshot onboarding through the driver documents API.

Use `documentType=driver_headshot` when uploading the image, then use admin review endpoints to approve/reject it.

## Base Path
- API prefix: `/api/v1`

## Driver Flow
### 1. Upload headshot
- Endpoint: `POST /api/v1/drivers/documents/upload`
- Auth: Driver bearer token
- Content type: `multipart/form-data`
- Required form fields:
  - `documentType`: `driver_headshot`
  - `file`: image file (for example `.jpg`, `.png`)

Example:
```bash
curl -X POST "http://localhost:7860/api/v1/drivers/documents/upload" \
  -H "Authorization: Bearer <DRIVER_ACCESS_TOKEN>" \
  -F "documentType=driver_headshot" \
  -F "file=@/path/to/headshot.jpg;type=image/jpeg"
```

Success response shape:
```json
{
  "status_code": 200,
  "detail": "Document uploaded",
  "data": {
    "id": "67c1040f8b3e9f0f6d0fcb2a",
    "driverId": "67c100f58b3e9f0f6d0fcb10",
    "documentType": "driver_headshot",
    "fileKey": "drivers/67c100f58b3e9f0f6d0fcb10/1736544242_headshot.jpg",
    "fileName": "headshot.jpg",
    "mimeType": "image/jpeg",
    "storageProvider": "s3",
    "signedUrl": "https://<signed-or-public-url>",
    "status": "pending",
    "uploadedAt": 1736544242
  }
}
```

Important behavior:
- If the latest `driver_headshot` is already `pending` or `approved`, this endpoint returns the existing document instead of creating a new one.
- Re-upload is expected after admin rejection (`status=rejected`).

### 2. Read latest headshot document
- Endpoint: `GET /api/v1/drivers/documents/latest`
- Auth: Driver bearer token

This returns the latest document per type, including `driver_headshot`.

## URL Handling (No Separate "Set URL" Endpoint)
There is no separate endpoint to manually set a headshot URL.

The API sets/derives URL metadata from storage:
- `fileKey` is stored for the uploaded file.
- `signedUrl` is included in document responses.
- For S3-compatible storage, signed URLs may rotate and are regenerated when listing documents.

If your client needs a current URL, fetch via:
- `GET /api/v1/drivers/documents`
- `GET /api/v1/drivers/documents/latest`

## Admin Flow (Headshot Review)
### 1. List pending headshots
- Endpoint: `GET /api/v1/admins/driver-documents/pending?documentType=driver_headshot`
- Optional query filter: `driverId=<driver_id>`
- Auth: Admin bearer token

### 2. Approve or reject a specific headshot
- Endpoint: `PATCH /api/v1/admins/driver/{driverId}/documents/{docId}`
- Auth: Admin bearer token
- JSON body:
  - `status`: `approved` or `rejected`
  - `reason`: optional text

Approve example:
```bash
curl -X PATCH "http://localhost:7860/api/v1/admins/driver/<DRIVER_ID>/documents/<DOC_ID>" \
  -H "Authorization: Bearer <ADMIN_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"status":"approved","reason":"Face is clear and matches profile"}'
```

Reject example:
```bash
curl -X PATCH "http://localhost:7860/api/v1/admins/driver/<DRIVER_ID>/documents/<DOC_ID>" \
  -H "Authorization: Bearer <ADMIN_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"status":"rejected","reason":"Blurry image, please upload a clearer photo"}'
```

## After Approval
- Approved headshots are used in driver ride snapshots (`driverHeadshotUrl`) and SSE driver snapshot payloads (`headshotUrl`).
- Driver operational eligibility checks require all required documents (including `driver_headshot`) to be approved.

## Related Admin Actions
- Driver account activation is separate:
  - `PATCH /api/v1/admins/approve/driver/{driverId}`

Headshot approval does not automatically set `accountStatus=active`; admin may still need to activate the driver account depending on onboarding policy.
