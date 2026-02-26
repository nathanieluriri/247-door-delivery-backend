from fastapi import HTTPException

from security.oauth_return import (
    build_oauth_state,
    parse_oauth_state_or_raise,
    resolve_default_frontend_base,
    resolve_return_url_or_raise,
)


def test_resolve_default_frontend_base_local_and_prod():
    assert (
        resolve_default_frontend_base("rider", backend_host="localhost")
        == "http://localhost:8080"
    )
    assert (
        resolve_default_frontend_base("driver", backend_host="127.0.0.1")
        == "http://localhost:8000"
    )
    assert (
        resolve_default_frontend_base(
            "rider", backend_host="backend.247doordelivery.co.uk"
        )
        == "https://rider.247doordelivery.co.uk"
    )
    assert (
        resolve_default_frontend_base(
            "driver", backend_host="backend.247doordelivery.co.uk"
        )
        == "https://driver.247doordelivery.co.uk"
    )


def test_resolve_return_url_allows_relative_path():
    resolved = resolve_return_url_or_raise(
        role="rider",
        backend_host="localhost",
        next_url="/auth/complete?from=google",
    )
    assert resolved == "http://localhost:8080/auth/complete?from=google"


def test_resolve_return_url_allows_local_cross_frontend_ports():
    driver_resolved = resolve_return_url_or_raise(
        role="driver",
        backend_host="localhost",
        next_url="http://localhost:8080/driver/wallet",
    )
    rider_resolved = resolve_return_url_or_raise(
        role="rider",
        backend_host="localhost",
        next_url="http://localhost:8000/auth/complete",
    )
    assert driver_resolved == "http://localhost:8080/driver/wallet"
    assert rider_resolved == "http://localhost:8000/auth/complete"


def test_resolve_return_url_rejects_non_allowlisted_origin():
    try:
        resolve_return_url_or_raise(
            role="rider",
            backend_host="backend.247doordelivery.co.uk",
            next_url="https://evil.example.com/pwn",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException for non-allowlisted URL")


def test_build_and_parse_oauth_state_roundtrip():
    state = build_oauth_state(
        role="driver",
        return_url="https://driver.247doordelivery.co.uk/dashboard",
    )
    return_url = parse_oauth_state_or_raise(
        role="driver",
        state=state,
        backend_host="backend.247doordelivery.co.uk",
    )
    assert return_url == "https://driver.247doordelivery.co.uk/dashboard"


def test_parse_oauth_state_rejects_role_mismatch():
    state = build_oauth_state(
        role="rider",
        return_url="https://rider.247doordelivery.co.uk",
    )
    try:
        parse_oauth_state_or_raise(
            role="driver",
            state=state,
            backend_host="backend.247doordelivery.co.uk",
        )
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected HTTPException for OAuth role mismatch")
