# Analysis for security

## Summary
- Authentication, JWT handling, permissions, and account status checks.

## Potential issues / gaps
- JWT signing and validation appear inconsistent between admin/member tokens.
- Secrets and lifetimes are partially hard-coded.
- No centralized audit logging or rate limiting for auth endpoints.

## Notes
- Token storage and refresh logic is implemented via Mongo collections.
