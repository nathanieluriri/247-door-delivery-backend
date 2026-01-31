# AV & IAM Hardening

## Plan
- Integrate ClamAV (sidecar/service) into upload path; quarantine on detection.
- Store hash metadata (SHA256/MD5) with documents; verify on download.
- Review/rotate R2 keys; document least-privilege IAM.

## Checks
- AV scanner invoked on uploads; infected files blocked/quarantined.
- Hashes saved and optionally verified on access.
- IAM review completed; keys rotated and documented.
