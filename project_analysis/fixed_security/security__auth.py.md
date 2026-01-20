# Analysis for security/auth.py

## Summary
- Authentication guards for riders, drivers, and admins.

## Potential issues / gaps
- Token decoding and role checks are inconsistent across functions.
- Some functions return decoded payloads while others return DB token objects.
- `verify_token` returns `JWTPayload` but relies on fields that may not exist.

## Notes
- Uses HTTP Bearer tokens and Mongo-backed token storage.
