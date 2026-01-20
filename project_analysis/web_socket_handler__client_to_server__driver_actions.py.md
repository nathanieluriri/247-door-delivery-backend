# Analysis for web_socket_handler/client_to_server/driver_actions.py

## Summary
- Driver status and location updates.

## Potential issues / gaps
- Location updates write to Redis without rate limiting or accuracy checks.
- No validation for stale or out-of-order location timestamps.

## Notes
- Adds drivers to a Redis geo index under `drivers:geo_index`.
