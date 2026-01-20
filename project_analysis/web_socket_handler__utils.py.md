# Analysis for web_socket_handler/utils.py

## Summary
- Helper functions for presence, role checks, and ride action logic.

## Potential issues / gaps
- `cache_db` is referenced but not imported in this file; `sync_cleanup_user` uses it.
- Mixed sync/async operations with Redis OM and DB calls; potential blocking.
- Driver/rider authorization checks rely on in-memory `authenticated_users` map.

## Notes
- Emits ride status updates for accept/start/complete/cancel flows.
