# Storage & Security

## Plan
- Enforce AV scanning + quarantine pipeline for uploads (ClamAV service).
- Ensure R2 presigned URLs only; remove any raw path returns.
- Hash every upload (SHA256/MD5) and persist with document metadata.
- Rotate R2 keys and capture IAM review checklist.

## Checks
- AV scanner blocks infected uploads; quarantines files.
- All downloads use presigned URLs; no file paths exposed.
- Hashes stored with each document record.
- IAM review completed; keys rotated and documented.
