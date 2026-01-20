# Analysis for main.py

## Summary
- FastAPI app assembly with middleware, rate limiting, health checks, and Socket.IO ASGI wrapper.

## Potential issues / gaps
- `get_access_tokens` is used but not imported; likely runtime error in `get_user_type`.
- Hard-coded SessionMiddleware secret and permissive CORS (`*`) are unsafe for production.
- Rate limiter depends on Redis but has no failure fallback; outage may block all requests.
- Health check triggers a Celery task each call, which can overload workers.
- Extensive `print` logging; no structured logging or request IDs.

## Notes
- Includes scheduler startup, Mongo/Redis health checks, and websocket app mount.
