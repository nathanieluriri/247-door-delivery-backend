import os
import secrets
import time
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

import jwt
from fastapi import HTTPException, status

Role = Literal["rider", "driver"]
STATE_AUDIENCE = "door-delivery-oauth-state"


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _normalize_origin(url_value: str) -> str | None:
    parsed = urlparse(url_value)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _csv_to_origins(raw_value: str | None) -> set[str]:
    if not raw_value:
        return set()
    origins: set[str] = set()
    for item in raw_value.split(","):
        normalized = _normalize_origin(item.strip())
        if normalized:
            origins.add(normalized)
    return origins


def _state_secret() -> str:
    return (
        os.getenv("OAUTH_STATE_SECRET")
        or os.getenv("SESSION_SECRET_KEY")
        or os.getenv("SECRET_KEY")
        or "super-secure-secret-key"
    )


def resolve_default_frontend_base(role: Role, backend_host: str) -> str:
    host = (backend_host or "").split(":", 1)[0].lower()
    is_local = host in {"localhost", "127.0.0.1"}
    is_247_domain = "247doordelivery.co.uk" in host

    if role == "rider":
        local_base = os.getenv("RIDER_FRONTEND_URL_LOCAL", "http://localhost:8080")
        prod_base = os.getenv(
            "RIDER_FRONTEND_URL_PROD", "https://rider.247doordelivery.co.uk"
        )
    else:
        local_base = os.getenv("DRIVER_FRONTEND_URL_LOCAL", "http://localhost:8000")
        prod_base = os.getenv(
            "DRIVER_FRONTEND_URL_PROD", "https://driver.247doordelivery.co.uk"
        )

    if is_local:
        return local_base.rstrip("/")
    if is_247_domain:
        return prod_base.rstrip("/")
    return local_base.rstrip("/")


def _allowlisted_origins(role: Role, backend_host: str) -> set[str]:
    base_url = resolve_default_frontend_base(role=role, backend_host=backend_host)
    defaults = {_normalize_origin(base_url)} if _normalize_origin(base_url) else set()
    shared_origins = _csv_to_origins(os.getenv("RETURN_URL_ALLOWLIST"))
    role_key = (
        "RIDER_RETURN_URL_ALLOWLIST" if role == "rider" else "DRIVER_RETURN_URL_ALLOWLIST"
    )
    role_origins = _csv_to_origins(os.getenv(role_key))
    return defaults | shared_origins | role_origins


def _absolute_return_url_or_none(
    role: Role,
    backend_host: str,
    next_url: str | None,
) -> str | None:
    if not next_url:
        return None

    candidate = next_url.strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    if not parsed.scheme and not parsed.netloc:
        if candidate.startswith("//"):
            return None
        base_url = resolve_default_frontend_base(role=role, backend_host=backend_host)
        return urljoin(f"{base_url}/", candidate.lstrip("/"))

    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return candidate


def resolve_return_url_or_raise(
    role: Role,
    backend_host: str,
    next_url: str | None,
) -> str:
    resolved = _absolute_return_url_or_none(
        role=role,
        backend_host=backend_host,
        next_url=next_url,
    )
    if resolved is None:
        if next_url is None:
            return resolve_default_frontend_base(role=role, backend_host=backend_host)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid return URL format",
        )

    allowlisted_origins = _allowlisted_origins(role=role, backend_host=backend_host)
    origin = _normalize_origin(resolved)
    if not origin or origin not in allowlisted_origins:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Return URL is not in the allowlist",
        )
    return resolved


def build_oauth_state(role: Role, return_url: str) -> str:
    ttl_seconds = max(_int_env("OAUTH_STATE_TTL_SECONDS", 600), 1)
    now = int(time.time())
    payload = {
        "aud": STATE_AUDIENCE,
        "role": role,
        "return_url": return_url,
        "iat": now,
        "exp": now + ttl_seconds,
        "nonce": secrets.token_urlsafe(10),
    }
    return jwt.encode(payload, _state_secret(), algorithm="HS256")


def parse_oauth_state_or_raise(
    role: Role,
    state: str | None,
    backend_host: str,
) -> str:
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth state",
        )
    try:
        payload = jwt.decode(
            state,
            _state_secret(),
            algorithms=["HS256"],
            audience=STATE_AUDIENCE,
        )
    except jwt.PyJWTError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        ) from err

    payload_role = payload.get("role")
    if payload_role != role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state role mismatch",
        )
    payload_return_url = payload.get("return_url")
    if not isinstance(payload_return_url, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth state return URL missing",
        )
    return resolve_return_url_or_raise(
        role=role,
        backend_host=backend_host,
        next_url=payload_return_url,
    )


def append_query_params(url: str, params: dict[str, str]) -> str:
    parts = urlsplit(url)
    query_params = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in params.items():
        query_params[key] = value
    encoded = urlencode(query_params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, encoded, parts.fragment))
