# Analysis for security/encrypting_jwt.py

## Summary
- JWT creation and decoding utilities.

## Potential issues / gaps
- Hard-coded `SECRET_KEY` alongside dynamic secrets; decode uses only the hard-coded key.
- `create_jwt_member_token` uses `datetime(minutes=15)` (invalid) instead of `timedelta`.
- Token payload fields differ between member/admin tokens (`accessToken` vs `access_token`).

## Notes
- Includes helper to choose a random secret key from DB.
