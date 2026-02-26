from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from core.staff_payment import get_staff_payment_service
from schemas.driver import DriverOut
from schemas.driver_onboarding import FakeOnboardingDraftIn


class _InsertResult:
    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class _OnboardingCollection:
    def __init__(self):
        self.docs: list[dict[str, Any]] = []

    async def create_index(self, *args, **kwargs):  # noqa: ANN001, ANN002
        return None

    async def find_one(self, filter_dict: dict[str, Any]):
        for doc in self.docs:
            if all(doc.get(key) == value for key, value in filter_dict.items()):
                return dict(doc)
        return None

    async def insert_one(self, document: dict[str, Any]):
        doc = dict(document)
        doc["_id"] = str(len(self.docs) + 1)
        self.docs.append(doc)
        return _InsertResult(inserted_id=doc["_id"])

    async def find_one_and_update(
        self,
        filter_dict: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
        return_document: Any = None,  # noqa: ARG002
    ):
        for idx, doc in enumerate(self.docs):
            if all(doc.get(key) == value for key, value in filter_dict.items()):
                updated = dict(doc)
                updated.update(update.get("$set", {}))
                self.docs[idx] = updated
                return dict(updated)

        if not upsert:
            return None

        created = dict(filter_dict)
        created.update(update.get("$setOnInsert", {}))
        created.update(update.get("$set", {}))
        created["_id"] = str(len(self.docs) + 1)
        self.docs.append(created)
        return dict(created)


class _FakeDB:
    def __init__(self):
        self.driver_onboarding_profiles = _OnboardingCollection()


@pytest.fixture
def fake_staff_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STAFF_PAYMENT_DEFAULT_PROVIDER", "fake")
    monkeypatch.setenv("FAKE_PAYMENT_BASE_URL", "http://localhost:7860")
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)


def _mock_driver() -> DriverOut:
    return DriverOut(
        id="driver_abc123",
        email="driver@example.com",
        password="secret",
    )


@pytest.mark.asyncio
async def test_staff_payment_service_requires_supported_provider(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STAFF_PAYMENT_DEFAULT_PROVIDER", "unknown")
    monkeypatch.delenv("PAYMENT_DEFAULT_PROVIDER", raising=False)
    with pytest.raises(RuntimeError):
        get_staff_payment_service()


@pytest.mark.asyncio
async def test_staff_payment_service_requires_fake_base_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STAFF_PAYMENT_DEFAULT_PROVIDER", "fake")
    monkeypatch.delenv("FAKE_PAYMENT_BASE_URL", raising=False)
    with pytest.raises(RuntimeError):
        get_staff_payment_service()


@pytest.mark.asyncio
async def test_fake_onboarding_complete_flow(fake_staff_env, monkeypatch: pytest.MonkeyPatch):
    fake_db = _FakeDB()
    monkeypatch.setattr("repositories.driver_onboarding_repo.db", fake_db)
    monkeypatch.setattr("repositories.driver_onboarding_repo._indexes_ready", False, raising=False)

    async def _noop_update_driver_by_id(*args, **kwargs):  # noqa: ANN001, ANN002
        return None

    monkeypatch.setattr("services.driver_service.update_driver_by_id", _noop_update_driver_by_id)

    service = get_staff_payment_service()
    driver = _mock_driver()

    onboarding = await service.onboard_driver(
        driver=driver,
        driver_access_token="driver.jwt.token",
        requested_return_url="http://localhost:8080/driver/wallet",
        backend_host="localhost",
    )

    assert onboarding["provider"] == "fake"
    assert "token=driver.jwt.token" in onboarding["onboarding_url"]

    draft_payload = FakeOnboardingDraftIn(
        personal={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "driver@example.com",
            "phone": "+447000000000",
            "dob_day": 10,
            "dob_month": 12,
            "dob_year": 1993,
        },
        address={
            "line1": "123 Main Street",
            "city": "London",
            "postal_code": "SW1A1AA",
            "country": "GB",
        },
        bank={
            "account_holder_name": "Ada Lovelace",
            "account_number": "12345678",
            "sort_code": "10-10-10",
        },
        attestations={
            "tos_accepted": True,
            "identity_confirmed": True,
            "information_accurate": True,
        },
    )

    saved = await service.save_fake_onboarding(
        driver=driver,
        payload=draft_payload,
        backend_host="localhost",
    )
    assert saved["status"] in {"in_progress", "completed"}
    assert saved["required_missing"] == []

    completed = await service.complete_fake_onboarding(
        driver=driver,
        payload=draft_payload,
        requested_return_url="http://localhost:8080/driver/wallet",
        backend_host="localhost",
    )
    assert completed["status"] == "completed"
    assert completed["redirect_url"] == "http://localhost:8080/driver/wallet"


@pytest.mark.asyncio
async def test_fake_onboarding_requires_required_fields(fake_staff_env, monkeypatch: pytest.MonkeyPatch):
    fake_db = _FakeDB()
    monkeypatch.setattr("repositories.driver_onboarding_repo.db", fake_db)
    monkeypatch.setattr("repositories.driver_onboarding_repo._indexes_ready", False, raising=False)

    async def _noop_update_driver_by_id(*args, **kwargs):  # noqa: ANN001, ANN002
        return None

    monkeypatch.setattr("services.driver_service.update_driver_by_id", _noop_update_driver_by_id)

    service = get_staff_payment_service()
    driver = _mock_driver()

    with pytest.raises(HTTPException) as exc:
        await service.complete_fake_onboarding(
            driver=driver,
            payload=FakeOnboardingDraftIn(),
            requested_return_url="http://localhost:8080/driver/wallet",
            backend_host="localhost",
        )

    assert exc.value.status_code == 400
