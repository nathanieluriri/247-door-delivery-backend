from __future__ import annotations

import json
import time
from typing import Any

from fastapi import HTTPException, status

from core.database import db

from .provider import PaymentProvider
from .types import (
    PaymentIntentRequest,
    PaymentIntentResponse,
    PaymentProviderName,
    PaymentStatus,
    PaymentTransaction,
    WebhookEvent,
)


class FakePaymentProvider(PaymentProvider):
    provider_name = PaymentProviderName.FAKE

    def __init__(self, base_url: str, webhook_secret_hash: str | None = None):
        self._base_url = base_url.rstrip("/")
        self._webhook_secret_hash = webhook_secret_hash

    @staticmethod
    def _epoch() -> int:
        return int(time.time())

    @staticmethod
    def _normalize_status(raw_status: Any) -> PaymentStatus:
        status_str = str(raw_status or "").strip().lower()
        if status_str in {"success", "successful", "succeeded"}:
            return PaymentStatus.SUCCEEDED
        if status_str == "failed":
            return PaymentStatus.FAILED
        if status_str == "refunded":
            return PaymentStatus.REFUNDED
        return PaymentStatus.PENDING

    def _build_checkout_url(self, reference: str) -> str:
        return f"{self._base_url}/api/web/payments/link/{reference}"

    async def _find_intent(self, reference: str) -> dict[str, Any]:
        intent = await db.test_payment_intent.find_one({"reference": reference})
        if intent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Test payment intent not found for reference '{reference}'",
            )
        return intent

    async def create_intent(self, payload: PaymentIntentRequest) -> PaymentIntentResponse:
        now = self._epoch()
        checkout_url = self._build_checkout_url(payload.reference)

        document = {
            "reference": payload.reference,
            "amount_minor": int(payload.amount_minor),
            "currency": payload.currency.upper(),
            "customer_email": payload.customer_email,
            "metadata": payload.metadata or {},
            "status": PaymentStatus.PENDING.value,
            "provider": self.provider_name.value,
            "created_at": now,
            "updated_at": now,
        }

        existing = await db.test_payment_intent.find_one({"reference": payload.reference})
        if existing is None:
            insert_result = await db.test_payment_intent.insert_one(document)
            if not getattr(insert_result, "acknowledged", False):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Fake payment provider failed to create payment intent",
                )
            intent_snapshot = document
        else:
            metadata = payload.metadata or existing.get("metadata") or {}
            await db.test_payment_intent.update_one(
                {"reference": payload.reference},
                {"$set": {"updated_at": now, "metadata": metadata}},
            )
            intent_snapshot = {**existing, "metadata": metadata, "updated_at": now}

        provider_payload = {
            "reference": intent_snapshot.get("reference", payload.reference),
            "amount_minor": int(intent_snapshot.get("amount_minor", payload.amount_minor)),
            "currency": str(intent_snapshot.get("currency", payload.currency)).upper(),
            "status": self._normalize_status(intent_snapshot.get("status")).value,
            "metadata": intent_snapshot.get("metadata") or {},
            "provider": self.provider_name.value,
            "checkout_url": checkout_url,
        }

        return PaymentIntentResponse(
            provider=self.provider_name,
            reference=payload.reference,
            status=PaymentStatus.PENDING,
            checkout_url=checkout_url,
            provider_payload=provider_payload,
        )

    async def verify_webhook(self, body: bytes, headers: dict[str, str]) -> WebhookEvent:
        provided_hash = headers.get("verif-hash") or headers.get("Verif-Hash")
        if self._webhook_secret_hash and provided_hash != self._webhook_secret_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid fake payment webhook signature",
            )

        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid fake payment webhook payload",
            ) from err

        reference = (
            payload.get("reference")
            or payload.get("tx_ref")
            or (payload.get("data") or {}).get("reference")
            or (payload.get("data") or {}).get("tx_ref")
        )

        event_id = str(payload.get("id") or payload.get("event_id") or reference or "unknown")
        event_type = str(payload.get("event") or payload.get("type") or payload.get("status") or "unknown")

        return WebhookEvent(
            provider=self.provider_name,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            reference=reference,
        )

    async def fetch_transaction(self, reference: str) -> PaymentTransaction:
        intent = await self._find_intent(reference)
        normalized_status = self._normalize_status(intent.get("status"))

        raw = {
            "reference": reference,
            "status": normalized_status.value,
            "amount_minor": int(intent.get("amount_minor", 0)),
            "currency": str(intent.get("currency", "USD")).upper(),
            "metadata": intent.get("metadata") or {},
            "provider": self.provider_name.value,
            "checkout_url": self._build_checkout_url(reference),
        }

        return PaymentTransaction(
            provider=self.provider_name,
            reference=reference,
            status=normalized_status,
            raw=raw,
        )

    async def refund(self, reference: str, amount_minor: int | None = None) -> PaymentTransaction:
        intent = await self._find_intent(reference)
        now = self._epoch()
        original_amount = int(intent.get("amount_minor", 0))
        refunded_amount = int(amount_minor) if amount_minor is not None else original_amount

        await db.test_payment_intent.update_one(
            {"reference": reference},
            {
                "$set": {
                    "status": PaymentStatus.REFUNDED.value,
                    "updated_at": now,
                    "refunded_amount_minor": refunded_amount,
                    "refund_requested_amount_minor": amount_minor,
                }
            },
        )

        raw = {
            "reference": reference,
            "status": PaymentStatus.REFUNDED.value,
            "refunded_amount_minor": refunded_amount,
            "refund_requested_amount_minor": amount_minor,
            "provider": self.provider_name.value,
        }

        return PaymentTransaction(
            provider=self.provider_name,
            reference=reference,
            status=PaymentStatus.REFUNDED,
            raw=raw,
        )

    async def complete_checkout(self, reference: str, status_value: str) -> PaymentTransaction:
        intent = await self._find_intent(reference)
        normalized_status = self._normalize_status(status_value)

        await db.test_payment_intent.update_one(
            {"reference": reference},
            {
                "$set": {
                    "status": normalized_status.value,
                    "updated_at": self._epoch(),
                }
            },
        )

        updated = {
            **intent,
            "status": normalized_status.value,
            "updated_at": self._epoch(),
        }

        raw = {
            "reference": reference,
            "status": normalized_status.value,
            "amount_minor": int(updated.get("amount_minor", 0)),
            "currency": str(updated.get("currency", "USD")).upper(),
            "metadata": updated.get("metadata") or {},
            "provider": self.provider_name.value,
            "checkout_url": self._build_checkout_url(reference),
        }

        return PaymentTransaction(
            provider=self.provider_name,
            reference=reference,
            status=normalized_status,
            raw=raw,
        )
