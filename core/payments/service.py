from __future__ import annotations

import time
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, Request, status

from core.metrics import payment_failures
from repositories.payment_repo import (
    create_payment_transaction,
    get_payment_transaction_by_provider_payment_id,
    get_payment_transaction_by_reference,
    get_payment_transaction_by_ride_id,
    is_webhook_event_processed,
    mark_webhook_event_processed,
    update_payment_transaction_status,
    upsert_payment_transaction_by_reference,
)
from repositories.ride import get_ride, update_ride
from schemas.imports import CheckoutSessionObject, InvoiceData, RideStatus, StripeEvent
from schemas.ride import RideUpdate
from services.sse_service import publish_ride_status_update
from services.stripe_event_service import add_stripe_event, retrieve_stripe_event_by_stripe_event_id

from .fake_provider import FakePaymentProvider
from .manager import PaymentManager
from .stripe_provider import StripePaymentProvider
from .types import PaymentIntentRequest, PaymentProviderName, PaymentStatus, PaymentTransaction, WebhookEvent


class PaymentService:
    def __init__(self):
        PaymentManager.configure_from_settings()

    @staticmethod
    def _ride_price_to_minor(price: float) -> int:
        return int(round(price / 10))

    @staticmethod
    def _extract_reference(payload: dict[str, Any]) -> str | None:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        data_obj = data.get("object") if isinstance(data.get("object"), dict) else {}
        metadata = data_obj.get("metadata") if isinstance(data_obj.get("metadata"), dict) else {}
        data_reference = data.get("reference") if isinstance(data, dict) else None
        data_tx_ref = data.get("tx_ref") if isinstance(data, dict) else None

        reference = (
            payload.get("reference")
            or payload.get("tx_ref")
            or data_reference
            or data_tx_ref
            or metadata.get("reference")
        )
        if reference:
            return str(reference)

        ride_id = metadata.get("ride_id")
        if ride_id:
            return f"ride:{ride_id}"

        return None

    @staticmethod
    def _extract_ride_id(reference: str | None, payload: dict[str, Any], db_tx: dict[str, Any] | None) -> str | None:
        if db_tx and db_tx.get("ride_id"):
            return str(db_tx["ride_id"])

        if reference and reference.startswith("ride:"):
            return reference.split(":", 1)[1]

        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        data_obj = data.get("object") if isinstance(data.get("object"), dict) else {}
        metadata = data_obj.get("metadata") if isinstance(data_obj.get("metadata"), dict) else {}
        ride_id = metadata.get("ride_id")
        return str(ride_id) if ride_id else None

    async def create_payment_link(self, ride_id: str) -> str:
        ride = await get_ride({"_id": ObjectId(ride_id)}) if ObjectId.is_valid(ride_id) else await get_ride({"_id": ride_id})
        if ride is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")

        if ride.paymentStatus:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fare has already been paid")
        if ride.price is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride price is missing")

        existing_by_ride = await get_payment_transaction_by_ride_id(ride.id)
        if existing_by_ride and isinstance(existing_by_ride.get("response_payload"), dict):
            checkout_url = existing_by_ride["response_payload"].get("checkout_url")
            if checkout_url:
                return str(checkout_url)

        provider = PaymentManager.get_provider(None)
        provider_name = PaymentManager.get_default_provider_name()

        reference = f"ride:{ride.id}"
        amount_minor = self._ride_price_to_minor(ride.price)
        metadata = {
            "ride_id": ride.id,
            "user_id": ride.userId,
            "title": "Door Delivery Ride",
            "description": f"Ride payment for {ride.id}",
        }

        payload = PaymentIntentRequest(
            reference=reference,
            amount_minor=amount_minor,
            currency="GBP",
            customer_email=None,
            metadata=metadata,
        )
        intent = await provider.create_intent(payload)

        existing_by_reference = await get_payment_transaction_by_reference(reference)
        base_document = {
            "owner_id": ride.userId,
            "ride_id": ride.id,
            "provider": provider_name,
            "reference": reference,
            "status": intent.status.value,
            "amount_minor": amount_minor,
            "currency": payload.currency,
            "response_payload": {
                **intent.provider_payload,
                "checkout_url": intent.checkout_url,
                "reference": intent.reference,
                "status": intent.status.value,
            },
            "provider_payment_id": intent.provider_payload.get("id") if isinstance(intent.provider_payload, dict) else None,
            "idempotency_key": f"{provider_name}:{reference}",
        }

        if existing_by_reference is None:
            await create_payment_transaction(base_document)
        else:
            await upsert_payment_transaction_by_reference(reference, base_document)

        return intent.checkout_url

    async def send_invoice(self, ride_id: str) -> dict[str, Any]:
        provider = PaymentManager.get_provider(None)
        if not isinstance(provider, StripePaymentProvider):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice generation is only supported when Stripe is the active payment provider",
            )

        ride = await get_ride({"_id": ObjectId(ride_id)}) if ObjectId.is_valid(ride_id) else await get_ride({"_id": ride_id})
        if ride is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")

        return await provider.generate_and_send_invoice(ride)

    async def refund(self, payment_intent_id: str, amount: int | None = None) -> dict[str, Any]:
        if not payment_intent_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment intent id is required")

        db_tx = await get_payment_transaction_by_provider_payment_id(payment_intent_id)
        if db_tx is None:
            db_tx = await get_payment_transaction_by_reference(payment_intent_id)

        provider_name = str(db_tx.get("provider")) if db_tx else PaymentManager.get_default_provider_name()
        provider = PaymentManager.get_provider(provider_name)

        reference = str(db_tx.get("reference")) if db_tx and db_tx.get("reference") else payment_intent_id
        tx = await provider.refund(reference=reference, amount_minor=amount)

        await upsert_payment_transaction_by_reference(
            reference,
            {
                "provider": provider_name,
                "status": tx.status.value,
                "response_payload": tx.raw,
                "provider_payment_id": tx.raw.get("payment_intent") or tx.raw.get("payment_intent_id") or payment_intent_id,
            },
        )
        return tx.raw

    async def webhook_handler(self, request: Request, provider: str) -> dict[str, Any]:
        payment_provider = PaymentManager.get_provider(provider)
        body = await request.body()
        headers = dict(request.headers)

        event = await payment_provider.verify_webhook(body, headers)
        provider_key = event.provider.value

        if await is_webhook_event_processed(provider_key, event.event_id):
            return {"status": "ignored_duplicate", "provider": provider_key, "event_id": event.event_id}

        reference = event.reference or self._extract_reference(event.payload)
        if not reference:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Webhook missing reference")

        tx = await payment_provider.fetch_transaction(reference)

        db_tx = await update_payment_transaction_status(reference, tx.status.value, tx.raw)
        if db_tx is None:
            db_tx = await upsert_payment_transaction_by_reference(
                reference,
                {
                    "provider": provider_key,
                    "status": tx.status.value,
                    "response_payload": tx.raw,
                    "provider_payment_id": tx.raw.get("payment_intent_id") or tx.raw.get("payment_intent"),
                },
            )

        await mark_webhook_event_processed(provider_key, event.event_id)
        await self._apply_webhook_side_effects(event, tx, db_tx, reference)

        return {
            "status": "success",
            "provider": provider_key,
            "event_id": event.event_id,
            "reference": reference,
            "payment_status": tx.status.value,
        }

    async def complete_fake_checkout(self, reference: str, checkout_status: str) -> dict[str, Any]:
        provider = PaymentManager.get_provider(PaymentProviderName.FAKE.value)
        if not isinstance(provider, FakePaymentProvider):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fake payment provider is not enabled",
            )

        tx = await provider.complete_checkout(reference=reference, status_value=checkout_status)
        db_tx = await update_payment_transaction_status(reference, tx.status.value, tx.raw)
        if db_tx is None:
            db_tx = await upsert_payment_transaction_by_reference(
                reference,
                {
                    "provider": PaymentProviderName.FAKE.value,
                    "status": tx.status.value,
                    "response_payload": tx.raw,
                },
            )

        event = WebhookEvent(
            provider=PaymentProviderName.FAKE,
            event_id=f"fake-checkout-{reference}-{int(time.time())}",
            event_type=f"fake.checkout.{tx.status.value}",
            payload={
                "reference": reference,
                "status": tx.status.value,
                "source": "fake_checkout_page",
            },
            reference=reference,
        )
        await self._apply_webhook_side_effects(event, tx, db_tx, reference)

        return {
            "status": "success",
            "provider": PaymentProviderName.FAKE.value,
            "reference": reference,
            "payment_status": tx.status.value,
        }

    async def _apply_webhook_side_effects(
        self,
        event: WebhookEvent,
        tx: PaymentTransaction,
        db_tx: dict[str, Any] | None,
        reference: str,
    ) -> None:
        ride_id = self._extract_ride_id(reference, event.payload, db_tx)
        if not ride_id:
            return

        ride = await get_ride({"_id": ObjectId(ride_id)}) if ObjectId.is_valid(ride_id) else await get_ride({"_id": ride_id})
        if ride is None:
            return

        update_fields: dict[str, Any] = {
            "last_updated": int(time.time()),
        }

        if tx.status == PaymentStatus.SUCCEEDED:
            update_fields["paymentStatus"] = True
            update_fields["paymentDueAtMs"] = None
            if ride.rideStatus in {RideStatus.awaitingPayment, RideStatus.paymentFailed}:
                update_fields["rideStatus"] = RideStatus.completed
            elif ride.rideStatus in {RideStatus.pendingPayment, RideStatus.findingDriver}:
                update_fields["rideStatus"] = RideStatus.matching
        elif tx.status == PaymentStatus.FAILED:
            update_fields["paymentStatus"] = False
            if ride.rideStatus in {RideStatus.awaitingPayment, RideStatus.completed}:
                update_fields["rideStatus"] = RideStatus.paymentFailed
        elif tx.status == PaymentStatus.REFUNDED:
            update_fields["paymentStatus"] = False

        if event.provider == PaymentProviderName.STRIPE:
            existing_event = await retrieve_stripe_event_by_stripe_event_id(event.event_id)
            if existing_event is None:
                await add_stripe_event({"stripe_id": event.event_id, "event": event.payload})

            try:
                stripe_event = StripeEvent(**event.payload)
                update_fields["stripeEvent"] = stripe_event
            except Exception:
                pass

            data_obj = ((event.payload.get("data") or {}).get("object") or {})
            if event.event_type == "checkout.session.completed":
                try:
                    checkout_session = CheckoutSessionObject(**data_obj)
                    update_fields["checkoutSessionObject"] = checkout_session
                except Exception:
                    pass
            elif event.event_type == "invoice.payment_succeeded":
                try:
                    invoice = InvoiceData(**data_obj)
                    update_fields["invoiceData"] = invoice
                    update_fields["paymentStatus"] = True
                except Exception:
                    pass
            elif event.event_type == "invoice.payment_failed":
                payment_failures.inc()

        if event.provider == PaymentProviderName.FAKE and tx.status == PaymentStatus.SUCCEEDED:
            checkout_payload = {
                "id": f"fake_cs_{reference}",
                "payment_status": "paid",
                "amount_total": db_tx.get("amount_minor") if db_tx else None,
                "currency": db_tx.get("currency", "gbp") if db_tx else "gbp",
                "payment_intent": reference,
                "payment_link": (
                    (db_tx.get("response_payload") or {}).get("checkout_url") if db_tx else None
                ),
                "metadata": {"ride_id": ride_id, "reference": reference},
            }
            update_fields["checkoutSessionObject"] = CheckoutSessionObject(**checkout_payload)

        ride_update = RideUpdate(**update_fields)
        updated = await update_ride(
            {"_id": ObjectId(ride_id)} if ObjectId.is_valid(ride_id) else {"_id": ride_id},
            ride_update,
        )

        if updated.rideStatus is not None and updated.rideStatus != ride.rideStatus:
            try:
                await publish_ride_status_update(
                    ride_id=ride_id,
                    status=updated.rideStatus,
                    rider_id=updated.userId,
                    driver_id=updated.driverId,
                    message=f"Payment status updated to {tx.status.value}",
                    eta_minutes=14,
                )
            except Exception:
                pass


_payment_service_singleton: PaymentService | None = None


def get_payment_service() -> PaymentService:
    global _payment_service_singleton
    if _payment_service_singleton is None:
        _payment_service_singleton = PaymentService()
    return _payment_service_singleton
