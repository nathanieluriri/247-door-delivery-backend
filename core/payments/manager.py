from __future__ import annotations

import os
from typing import Final

from fastapi import HTTPException, status

from .provider import PaymentProvider
from .types import PaymentProviderName

_DEFAULT_PROVIDER: Final[str] = PaymentProviderName.STRIPE.value


class PaymentManager:
    _providers: dict[str, PaymentProvider] = {}
    _default_provider: str | None = None

    @classmethod
    def configure_from_settings(cls, *, force: bool = False) -> None:
        if cls._providers and not force:
            return

        from .fake_provider import FakePaymentProvider
        from .stripe_provider import StripePaymentProvider

        providers: dict[str, PaymentProvider] = {}

        stripe_api_key = (os.getenv("STRIPE_API_KEY") or "").strip()
        if stripe_api_key:
            providers[PaymentProviderName.STRIPE.value] = StripePaymentProvider(
                api_key=stripe_api_key,
                webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET"),
                success_redirect_url=(
                    os.getenv("FRONTEND_SUCCESS_URL")
                    or "http://localhost:8080/payment/success"
                ),
                tax_rate_id=os.getenv("STRIPE_TAX_RATE_ID"),
            )

        fake_base_url = (os.getenv("FAKE_PAYMENT_BASE_URL") or "").strip()
        if fake_base_url:
            providers[PaymentProviderName.FAKE.value] = FakePaymentProvider(
                base_url=fake_base_url,
                webhook_secret_hash=os.getenv("FAKE_PAYMENT_WEBHOOK_SECRET_HASH"),
            )

        if not providers:
            raise RuntimeError(
                "At least one payment provider must be configured. "
                "Set STRIPE_API_KEY and/or FAKE_PAYMENT_BASE_URL."
            )

        configured_default = (os.getenv("PAYMENT_DEFAULT_PROVIDER") or _DEFAULT_PROVIDER).strip().lower()
        if configured_default not in providers:
            configured_default = next(iter(providers))

        cls._providers = providers
        cls._default_provider = configured_default

    @classmethod
    def _ensure_configured(cls) -> None:
        if not cls._providers:
            cls.configure_from_settings()

    @classmethod
    def list_providers(cls) -> list[str]:
        cls._ensure_configured()
        return list(cls._providers.keys())

    @classmethod
    def get_default_provider_name(cls) -> str:
        cls._ensure_configured()
        if cls._default_provider is None:
            raise RuntimeError("Payment manager default provider is not configured")
        return cls._default_provider

    @classmethod
    def get_provider(cls, provider: str | None = None) -> PaymentProvider:
        cls._ensure_configured()

        key = (provider or cls._default_provider or "").strip().lower()
        if key not in cls._providers:
            supported = ", ".join(sorted(cls._providers))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported payment provider '{key}'. Supported: {supported}",
            )
        return cls._providers[key]


def configure_payment_manager(*, force: bool = False) -> None:
    PaymentManager.configure_from_settings(force=force)
