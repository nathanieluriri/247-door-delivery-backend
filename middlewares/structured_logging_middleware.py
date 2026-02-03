import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("app.request")


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = int((time.time() - start) * 1000)
            path_params = request.scope.get("path_params") or {}
            log_payload = {
                "method": request.method,
                "path": request.url.path,
                "status": getattr(response, "status_code", None),
                "duration_ms": duration_ms,
                "ride_id": path_params.get("ride_id") or path_params.get("rideId"),
                "driver_id": path_params.get("driver_id") or path_params.get("driverId"),
                "rider_id": path_params.get("rider_id") or path_params.get("riderId"),
                "request_id": request.headers.get("x-request-id"),
            }
            logger.info("request", extra=log_payload)
