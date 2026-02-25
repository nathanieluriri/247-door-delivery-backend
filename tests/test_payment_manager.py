import pytest
from fastapi import HTTPException

from core.payments.manager import PaymentManager


@pytest.mark.asyncio
async def test_payment_manager_configures_fake_provider(monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    monkeypatch.setenv("FAKE_PAYMENT_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("PAYMENT_DEFAULT_PROVIDER", "fake")

    PaymentManager.configure_from_settings(force=True)

    assert PaymentManager.get_default_provider_name() == "fake"
    assert "fake" in PaymentManager.list_providers()


@pytest.mark.asyncio
async def test_payment_manager_rejects_unknown_provider(monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    monkeypatch.setenv("FAKE_PAYMENT_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("PAYMENT_DEFAULT_PROVIDER", "fake")

    PaymentManager.configure_from_settings(force=True)

    with pytest.raises(HTTPException) as exc:
        PaymentManager.get_provider("unknown")

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_payment_manager_requires_at_least_one_provider(monkeypatch):
    monkeypatch.delenv("STRIPE_API_KEY", raising=False)
    monkeypatch.delenv("FAKE_PAYMENT_BASE_URL", raising=False)

    with pytest.raises(RuntimeError):
        PaymentManager.configure_from_settings(force=True)
