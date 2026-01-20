# Analysis for web_socket_handler/broadcasts

## Summary
- Broadcast helpers for dispatching ride requests.

## Potential issues / gaps
- No priority queueing, fairness, or load balancing for matching.
- No per-driver throttling or backoff if a driver is flooded.

## Notes
- Uses Redis geo index for nearby driver lookup.
