from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from starlette.concurrency import run_in_threadpool

from schemas.imports import InvoiceData
from schemas.ride import RideOut

from .provider import PaymentProvider
from .types import (
    PaymentIntentRequest,
    PaymentIntentResponse,
    PaymentProviderName,
    PaymentStatus,
    PaymentTransaction,
    WebhookEvent,
)


class StripePaymentProvider(PaymentProvider):
    provider_name = PaymentProviderName.STRIPE

    def __init__(
        self,
        api_key: str,
        webhook_secret: str | None,
        success_redirect_url: str,
        tax_rate_id: str | None = None,
    ):
        try:
            import stripe  # type: ignore
        except ModuleNotFoundError as err:
            raise RuntimeError("stripe package is required for StripePaymentProvider") from err

        self._stripe = stripe
        self._stripe.api_key = api_key
        self._webhook_secret = webhook_secret
        self._success_redirect_url = success_redirect_url
        self._tax_rate_id = tax_rate_id

    @staticmethod
    def _normalize_status(raw_status: Any) -> PaymentStatus:
        status_str = str(raw_status or "").strip().lower()
        if status_str in {"succeeded", "paid"}:
            return PaymentStatus.SUCCEEDED
        if status_str in {"canceled", "cancelled", "requires_payment_method"}:
            return PaymentStatus.FAILED
        if status_str in {"refunded"}:
            return PaymentStatus.REFUNDED
        return PaymentStatus.PENDING

    async def create_intent(self, payload: PaymentIntentRequest) -> PaymentIntentResponse:
        if payload.amount_minor <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount must be greater than zero",
            )

        metadata = {**(payload.metadata or {}), "reference": payload.reference}
        product_name = str(metadata.get("title") or "Door Delivery Ride")
        description = str(metadata.get("description") or f"Payment reference {payload.reference}")[:500]

        line_item: dict[str, Any] = {
            "price_data": {
                "currency": payload.currency.lower(),
                "unit_amount": int(payload.amount_minor),
                "product_data": {
                    "name": product_name,
                    "description": description,
                },
            },
            "quantity": 1,
        }

        if self._tax_rate_id:
            line_item["tax_rates"] = [self._tax_rate_id]

        idempotency_key = f"payment_link:{payload.reference}"
        payment_link = await run_in_threadpool(
            self._stripe.PaymentLink.create,
            line_items=[line_item],
            after_completion={
                "type": "redirect",
                "redirect": {"url": self._success_redirect_url},
            },
            metadata=metadata,
            idempotency_key=idempotency_key,
        )

        provider_payload = {
            "id": getattr(payment_link, "id", None),
            "url": getattr(payment_link, "url", None),
            "metadata": getattr(payment_link, "metadata", {}) or {},
        }

        return PaymentIntentResponse(
            provider=self.provider_name,
            reference=payload.reference,
            status=PaymentStatus.PENDING,
            checkout_url=str(getattr(payment_link, "url", "")),
            provider_payload=provider_payload,
        )

    async def verify_webhook(self, body: bytes, headers: dict[str, str]) -> WebhookEvent:
        signature = headers.get("stripe-signature") or headers.get("Stripe-Signature")
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing Stripe signature",
            )

        if not self._webhook_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stripe webhook secret not configured",
            )

        try:
            event = self._stripe.Webhook.construct_event(body, signature, self._webhook_secret)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Stripe payload",
            ) from err
        except self._stripe.error.SignatureVerificationError as err:  # type: ignore[attr-defined]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Stripe signature",
            ) from err

        payload = dict(event)
        data_object = (payload.get("data") or {}).get("object") or {}
        metadata = data_object.get("metadata") or {}

        reference = metadata.get("reference")
        ride_id = metadata.get("ride_id")
        if not reference and ride_id:
            reference = f"ride:{ride_id}"

        event_id = str(payload.get("id") or "unknown")
        event_type = str(payload.get("type") or "unknown")

        return WebhookEvent(
            provider=self.provider_name,
            event_id=event_id,
            event_type=event_type,
            payload=payload,
            reference=reference,
        )

    async def fetch_transaction(self, reference: str) -> PaymentTransaction:
        payment_intent = None
        query = f"metadata['reference']:'{reference}'"

        try:
            result = await run_in_threadpool(
                self._stripe.PaymentIntent.search,
                query=query,
                limit=1,
            )
            if result and getattr(result, "data", None):
                payment_intent = result.data[0]
        except Exception:
            payment_intent = None

        if payment_intent is None and reference.startswith("ride:"):
            ride_id = reference.split(":", 1)[1]
            try:
                result = await run_in_threadpool(
                    self._stripe.PaymentIntent.search,
                    query=f"metadata['ride_id']:'{ride_id}'",
                    limit=1,
                )
                if result and getattr(result, "data", None):
                    payment_intent = result.data[0]
            except Exception:
                payment_intent = None

        if payment_intent is None and reference.startswith("pi_"):
            try:
                payment_intent = await run_in_threadpool(self._stripe.PaymentIntent.retrieve, reference)
            except Exception:
                payment_intent = None

        if payment_intent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stripe transaction not found for reference '{reference}'",
            )

        status_value = self._normalize_status(getattr(payment_intent, "status", None))
        raw = {
            "payment_intent_id": getattr(payment_intent, "id", None),
            "status": getattr(payment_intent, "status", None),
            "amount": getattr(payment_intent, "amount", None),
            "currency": getattr(payment_intent, "currency", None),
            "metadata": getattr(payment_intent, "metadata", None) or {},
            "provider": self.provider_name.value,
        }

        resolved_reference = reference
        metadata = raw.get("metadata") or {}
        if metadata.get("reference"):
            resolved_reference = str(metadata["reference"])
        elif metadata.get("ride_id"):
            resolved_reference = f"ride:{metadata['ride_id']}"

        return PaymentTransaction(
            provider=self.provider_name,
            reference=resolved_reference,
            status=status_value,
            raw=raw,
        )

    async def refund(self, reference: str, amount_minor: int | None = None) -> PaymentTransaction:
        payment_intent_id = reference
        if not reference.startswith("pi_"):
            tx = await self.fetch_transaction(reference)
            payment_intent_id = str(tx.raw.get("payment_intent_id") or "")

        if not payment_intent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to resolve Stripe payment intent for refund",
            )

        refund_kwargs: dict[str, Any] = {
            "payment_intent": payment_intent_id,
            "idempotency_key": f"refund:{payment_intent_id}:{amount_minor or 'full'}",
        }
        if amount_minor is not None:
            refund_kwargs["amount"] = int(amount_minor)

        try:
            refund = await run_in_threadpool(self._stripe.Refund.create, **refund_kwargs)
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe refund failed: {err}",
            ) from err

        refund_status = str(getattr(refund, "status", "pending")).lower()
        mapped_status = PaymentStatus.REFUNDED if refund_status == "succeeded" else PaymentStatus.PENDING

        raw = {
            "refund_id": getattr(refund, "id", None),
            "status": refund_status,
            "payment_intent": payment_intent_id,
            "provider": self.provider_name.value,
        }

        return PaymentTransaction(
            provider=self.provider_name,
            reference=reference,
            status=mapped_status,
            raw=raw,
        )

    async def generate_and_send_invoice(self, ride: RideOut) -> dict[str, Any]:
        from services.rider_service import retrieve_rider_by_rider_id

        if ride.paymentStatus:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ride has already been paid")

        rider = await retrieve_rider_by_rider_id(id=ride.userId)
        rider_email = getattr(rider, "email", None)
        if not rider_email:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rider email not found")

        if ride.price is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ride price is missing")

        amount_minor = int(round(ride.price / 10))
        stops_summary = " -> ".join(ride.stops) if ride.stops else "No stops"
        description = (
            f"Pickup: {ride.pickup}\n"
            f"Destination: {ride.destination}\n"
            f"Stops: {stops_summary}\n"
            f"Distance: {ride.map.totalDistanceMeters / 1000:.1f} km\n"
            f"Duration: {ride.map.totalDurationSeconds // 60} mins\n"
        )

        customers = await run_in_threadpool(
            self._stripe.Customer.search,
            query=f"email:'{rider_email}'",
            limit=1,
        )

        if customers.data:
            customer = customers.data[0]
        else:
            customer = await run_in_threadpool(
                self._stripe.Customer.create,
                email=rider_email,
                name=f"{rider.firstName} {rider.lastName}".strip(),
                metadata={"rider_id": rider.id},
            )

        invoice = await run_in_threadpool(
            self._stripe.Invoice.create,
            customer=customer.id,
            auto_advance=True,
            collection_method="send_invoice",
            days_until_due=0,
            metadata={"ride_id": ride.id, "rider_id": rider.id},
            idempotency_key=f"ride:{ride.id}:invoice",
        )

        invoice_item_kwargs: dict[str, Any] = {
            "customer": customer.id,
            "invoice": invoice.id,
            "amount": amount_minor,
            "currency": "gbp",
            "description": description,
            "metadata": {"ride_id": ride.id, "rider_id": rider.id},
            "idempotency_key": f"ride:{ride.id}:invoice_item",
        }
        if self._tax_rate_id:
            invoice_item_kwargs["tax_rates"] = [self._tax_rate_id]

        await run_in_threadpool(self._stripe.InvoiceItem.create, **invoice_item_kwargs)
        finalized_invoice = await run_in_threadpool(self._stripe.Invoice.finalize_invoice, invoice.id)

        invoice_out = InvoiceData(
            id=finalized_invoice.id,
            status=getattr(finalized_invoice, "status", None),
            amount_paid=getattr(finalized_invoice, "amount_paid", None),
            currency=getattr(finalized_invoice, "currency", None),
            customer=getattr(finalized_invoice, "customer", None),
            metadata=getattr(finalized_invoice, "metadata", None) or {},
            email_sent_to=rider_email,
            invoice_url=getattr(finalized_invoice, "hosted_invoice_url", None),
        )
        return invoice_out.model_dump(by_alias=True)
