from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from schemas.driver import DriverBase
from schemas.imports import AccountStatus
from services import driver_service


class DummyDriver:
    def __init__(self, *, user_id: str = "driver-1", password: str = "hashed-password"):
        self.id = user_id
        self.password = password
        self.accountStatus = AccountStatus.ACTIVE
        self.access_token = None
        self.refresh_token = None


@pytest.mark.asyncio
async def test_authenticate_driver_oauth_existing_password_driver_succeeds_without_password(
    monkeypatch,
):
    driver = DummyDriver()

    async def fake_get_driver(filter_dict: dict):
        assert filter_dict == {"email": "driver@example.com"}
        return driver

    async def fake_add_access_tokens(token_data):
        assert token_data.userId == driver.id
        return SimpleNamespace(accesstoken="db-access")

    async def fake_add_refresh_tokens(token_data):
        assert token_data.userId == driver.id
        assert token_data.previousAccessToken == "db-access"
        return SimpleNamespace(refreshtoken="db-refresh")

    monkeypatch.setattr(driver_service, "get_driver", fake_get_driver)
    monkeypatch.setattr(driver_service, "add_access_tokens", fake_add_access_tokens)
    monkeypatch.setattr(driver_service, "add_refresh_tokens", fake_add_refresh_tokens)
    monkeypatch.setattr(
        driver_service,
        "create_jwt_token",
        lambda **_kwargs: "jwt-access",
    )

    result = await driver_service.authenticate_driver_oauth(
        email=" Driver@Example.com ",
        email_verified=True,
    )

    assert result is driver
    assert result.access_token == "jwt-access"
    assert result.refresh_token == "db-refresh"


@pytest.mark.asyncio
async def test_authenticate_driver_oauth_missing_email_fails(monkeypatch):
    called = {"get_driver": False}

    async def fake_get_driver(filter_dict: dict):
        assert isinstance(filter_dict, dict)
        called["get_driver"] = True
        return None

    monkeypatch.setattr(driver_service, "get_driver", fake_get_driver)

    with pytest.raises(HTTPException) as exc:
        await driver_service.authenticate_driver_oauth(email=" ", email_verified=True)

    assert exc.value.status_code == 400
    assert called["get_driver"] is False


@pytest.mark.asyncio
async def test_authenticate_driver_oauth_unverified_email_fails(monkeypatch):
    called = {"get_driver": False}

    async def fake_get_driver(filter_dict: dict):
        assert isinstance(filter_dict, dict)
        called["get_driver"] = True
        return None

    monkeypatch.setattr(driver_service, "get_driver", fake_get_driver)

    with pytest.raises(HTTPException) as exc:
        await driver_service.authenticate_driver_oauth(
            email="driver@example.com",
            email_verified=False,
        )

    assert exc.value.status_code == 401
    assert called["get_driver"] is False


@pytest.mark.asyncio
async def test_authenticate_driver_oauth_driver_not_found_fails(monkeypatch):
    async def fake_get_driver(filter_dict: dict):
        assert filter_dict == {"email": "driver@example.com"}
        return None

    monkeypatch.setattr(driver_service, "get_driver", fake_get_driver)

    with pytest.raises(HTTPException) as exc:
        await driver_service.authenticate_driver_oauth(
            email="driver@example.com",
            email_verified=True,
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_authenticate_driver_wrong_password_still_fails(monkeypatch):
    driver = DummyDriver(password="hashed-password")

    async def fake_get_driver(filter_dict: dict):
        assert filter_dict == {"email": "driver@example.com"}
        return driver

    monkeypatch.setattr(driver_service, "get_driver", fake_get_driver)
    monkeypatch.setattr(driver_service, "check_password", lambda **_kwargs: False)

    with pytest.raises(HTTPException) as exc:
        await driver_service.authenticate_driver(
            user_data=DriverBase(email="driver@example.com", password="bad-password")
        )

    assert exc.value.status_code == 401
