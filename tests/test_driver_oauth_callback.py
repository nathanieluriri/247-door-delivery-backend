from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

driver_route = pytest.importorskip("api.v1.driver")
from security.oauth_return import build_oauth_state


class FakeGoogleDriver:
    def __init__(self, userinfo: dict | None):
        self.userinfo = userinfo

    async def authorize_redirect(self, request, redirect_uri: str, state: str):
        return RedirectResponse(url=f"{redirect_uri}?state={state}", status_code=302)

    async def authorize_access_token(self, request):
        return {"userinfo": self.userinfo}


class FakeOAuth:
    def __init__(self, userinfo: dict | None):
        self.google_driver = FakeGoogleDriver(userinfo)


def _query_params(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


def _oauth_state_from_redirect(response) -> str:
    location = response.headers["location"]
    return _query_params(location)["state"][0]


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")
    app.include_router(driver_route.router, prefix="/api/v1")
    return TestClient(app)


def _start_google_login(client: TestClient, next_url: str = "http://localhost:8000/finish"):
    return client.get(
        "/api/v1/drivers/google/auth",
        params={"next": next_url},
        follow_redirects=False,
    )


def test_driver_google_callback_existing_driver_success(monkeypatch, client):
    monkeypatch.setattr(
        driver_route,
        "oauth",
        FakeOAuth({"email": "driver@example.com", "email_verified": True}),
    )

    async def fake_authenticate_driver_oauth(email: str, email_verified: bool | None = None):
        assert email == "driver@example.com"
        assert email_verified is True
        return SimpleNamespace(access_token="jwt-access", refresh_token="db-refresh")

    async def fail_add_driver(*_args, **_kwargs):
        raise AssertionError("add_driver should not be called for existing driver")

    async def fail_password_auth(*_args, **_kwargs):
        raise AssertionError("password auth should not be used in OAuth callback")

    monkeypatch.setattr(driver_route, "authenticate_driver_oauth", fake_authenticate_driver_oauth)
    monkeypatch.setattr(driver_route, "add_driver", fail_add_driver)
    monkeypatch.setattr(driver_route, "authenticate_driver", fail_password_auth)

    start = _start_google_login(client)
    state = _oauth_state_from_redirect(start)

    response = client.get(
        "/api/v1/drivers/auth/callback",
        params={"state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    params = _query_params(response.headers["location"])
    assert params["status"] == ["success"]
    assert params["access_token"] == ["jwt-access"]
    assert params["refresh_token"] == ["db-refresh"]


def test_driver_google_callback_new_driver_created_when_oauth_auth_not_found(monkeypatch, client):
    monkeypatch.setattr(
        driver_route,
        "oauth",
        FakeOAuth(
            {
                "email": "newdriver@example.com",
                "email_verified": True,
                "given_name": "New",
                "family_name": "Driver",
            }
        ),
    )
    captured = {}

    async def fake_authenticate_driver_oauth(_email: str, email_verified: bool | None = None):
        assert email_verified is True
        raise HTTPException(status_code=404, detail="User not found")

    async def fake_add_driver(driver_data):
        captured["email"] = driver_data.email
        captured["firstName"] = driver_data.firstName
        captured["lastName"] = driver_data.lastName
        return SimpleNamespace(access_token="new-jwt", refresh_token="new-refresh")

    monkeypatch.setattr(driver_route, "authenticate_driver_oauth", fake_authenticate_driver_oauth)
    monkeypatch.setattr(driver_route, "add_driver", fake_add_driver)

    start = _start_google_login(client)
    state = _oauth_state_from_redirect(start)

    response = client.get(
        "/api/v1/drivers/auth/callback",
        params={"state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    params = _query_params(response.headers["location"])
    assert params["status"] == ["success"]
    assert params["access_token"] == ["new-jwt"]
    assert params["refresh_token"] == ["new-refresh"]
    assert captured == {
        "email": "newdriver@example.com",
        "firstName": "New",
        "lastName": "Driver",
    }


def test_driver_google_callback_missing_email_redirects_oauth_user_info_missing(monkeypatch, client):
    monkeypatch.setattr(
        driver_route,
        "oauth",
        FakeOAuth({"email_verified": True}),
    )

    start = _start_google_login(client)
    state = _oauth_state_from_redirect(start)

    response = client.get(
        "/api/v1/drivers/auth/callback",
        params={"state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    params = _query_params(response.headers["location"])
    assert params["status"] == ["failed"]
    assert params["reason"] == ["oauth_user_info_missing"]


def test_driver_google_callback_state_mismatch_redirects_failure(monkeypatch, client):
    monkeypatch.setattr(
        driver_route,
        "oauth",
        FakeOAuth({"email": "driver@example.com", "email_verified": True}),
    )

    async def fake_authenticate_driver_oauth(email: str, email_verified: bool | None = None):
        return SimpleNamespace(access_token="jwt-access", refresh_token="db-refresh")

    monkeypatch.setattr(driver_route, "authenticate_driver_oauth", fake_authenticate_driver_oauth)

    start = _start_google_login(client)
    assert start.status_code == 302

    mismatched_state = build_oauth_state(
        role="driver",
        return_url="http://localhost:8000/finish",
    )
    response = client.get(
        "/api/v1/drivers/auth/callback",
        params={"state": mismatched_state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    params = _query_params(response.headers["location"])
    assert params["status"] == ["failed"]
    assert params["reason"] == ["oauth_state_mismatch"]


def test_driver_google_callback_unverified_email_redirects_callback_failed(monkeypatch, client):
    monkeypatch.setattr(
        driver_route,
        "oauth",
        FakeOAuth({"email": "driver@example.com", "email_verified": False}),
    )

    async def fake_authenticate_driver_oauth(_email: str, email_verified: bool | None = None):
        assert email_verified is False
        raise HTTPException(status_code=401, detail="Unverified email")

    monkeypatch.setattr(driver_route, "authenticate_driver_oauth", fake_authenticate_driver_oauth)

    start = _start_google_login(client)
    state = _oauth_state_from_redirect(start)

    response = client.get(
        "/api/v1/drivers/auth/callback",
        params={"state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    params = _query_params(response.headers["location"])
    assert params["status"] == ["failed"]
    assert params["reason"] == ["oauth_callback_failed"]
