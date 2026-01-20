# Analysis for web_socket_handler

## Summary
- Socket.IO server with driver/rider realtime events and Redis-backed presence.

## Potential issues / gaps
- Auth session data is in memory; loses state on restart.
- No per-event rate limits, ack timeouts, or retry guarantees for dispatch.
- Broadcast logic is basic radius-based without load balancing or fairness.

## Notes
- Redis is used for geo index and presence via Redis OM.
