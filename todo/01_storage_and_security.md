# Storage & Document Security

## Plan
- Migrate driver document storage from local disk to S3 (or compatible object store) with private buckets.
- Add antivirus/scan step on upload (e.g., ClamAV/Lambda hook) and reject malicious files.
- Store signed download URLs with short TTL; never expose raw paths.
- Encrypt sensitive metadata at rest where supported.

## Checks (Done When)
- Upload pipeline saves to S3 and returns stable object keys/URLs.
- Each upload is virus-scanned before acceptance.
- Download access requires signed URL; local filesystem path is no longer returned.
- Bucket IAM/policy reviewed and least-privilege in place.
