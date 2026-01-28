from starlette.middleware.base import BaseHTTPMiddleware
import math
import time
from fastapi import Request
from fastapi.responses import JSONResponse

from repositories.tokens_repo import get_access_tokens
from security.encrypting_jwt import decode_jwt_token
from schemas.response_schema import APIResponse


async def get_user_type(request: Request) -> tuple[str, str]:
    auth_header = request.headers.get("Authorization")

    # Anonymous fallback
    if not auth_header or not auth_header.startswith("Bearer "):
        ip = request.headers.get("X-Forwarded-For", request.client.host) # type: ignore
        return ip, "anonymous"

    token = auth_header.split(" ", 1)[1]

    try:
        decoded = await decode_jwt_token(token=token)
        if decoded is None:
            
            raise
        # 🔑 normalize admin vs member JWTs
        access_token_value = (
            decoded.get("access_token",None)
            or decoded.get("accessToken",None)
        )

        if not access_token_value:
            raise ValueError("access token missing in JWT")

        access_token = await get_access_tokens(
            accessToken=access_token_value
        )
        if (access_token == None) or (access_token.role==None):
            raise
        return access_token.userId, access_token.role

    except Exception:
        ip = request.headers.get("X-Forwarded-For", request.client.host) # type: ignore
        return ip, "anonymous"


class RateLimitingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id, user_type = await get_user_type(request)
        rate_limits = getattr(request.app.state, "rate_limits", None)
        limiter = getattr(request.app.state, "limiter", None)
        if not rate_limits or not limiter:
            return JSONResponse(
                status_code=500,
                content=APIResponse(
                    status_code=500,
                    data=None,
                    detail="Rate limiter not configured",
                ).dict(),
            )

        if user_type not in rate_limits:
            user_type = "anonymous"

        rate_limit_rule = rate_limits[user_type]

        # hit() → True if still under limit
        allowed = limiter.hit(rate_limit_rule, user_id)

        # Get current window stats (reset_time, remaining)
        reset_time, remaining = limiter.get_window_stats(rate_limit_rule, user_id)
        seconds_until_reset = max(math.ceil(reset_time - time.time()), 0)

        if not allowed:
            return JSONResponse(
                status_code=429,
                headers={
                    "X-User-Type": user_type,
                    "X-User-Id":user_id,
                    "X-RateLimit-Limit": str(rate_limit_rule.amount),
                    "X-RateLimit-Remaining": str(max(remaining, 0)),
                    "X-RateLimit-Reset": str(seconds_until_reset),
                    "Retry-After": str(seconds_until_reset),
                },
                content=APIResponse(
                    status_code=429,
                    data={
                        "retry_after_seconds": seconds_until_reset,
                        "user_type": user_type,
                    },
                    detail="Too Many Requests",
                ).dict(),
            )

        # Normal flow
        response = await call_next(request)

        # Add rate-limit headers for successful requests too
        response.headers["X-User-Id"]=user_id
        response.headers["X-User-Type"] = user_type
        response.headers["X-RateLimit-Limit"] = str(rate_limit_rule.amount)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        response.headers["X-RateLimit-Reset"] = str(seconds_until_reset)

        return response
