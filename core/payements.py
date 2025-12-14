import os
from dotenv import load_dotenv
from abc import ABC, abstractmethod
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
import stripe

from schemas.ride import RideOut
from schemas.rider_schema import RiderOut

load_dotenv()

VAT_TAX_RATE_ID = os.getenv("STRIPE_TAX_RATE_ID")


class PaymentProvider(ABC):
    @abstractmethod
    async def create_payment_link(self, ride: RideOut) -> str:
        pass

    @abstractmethod
    async def generate_and_send_invoice(self, ride: RideOut) -> dict:
        pass

    @abstractmethod
    async def refund_payment(self, payment_intent_id: str, amount: int = None) -> dict:
        pass


class StripePaymentProvider(PaymentProvider):
    def __init__(self, api_key: str, success_redirect_url: str):
        stripe.api_key = api_key
        self.success_redirect_url = success_redirect_url

    async def create_payment_link(self, ride: RideOut) -> str:
        if ride.paymentStatus:
            raise HTTPException(status_code=409, detail="Fare has already been paid.")

        stops_summary = " → ".join(ride.stops) if ride.stops else "No stops"
        trip_description = (
            f"Pickup: {ride.pickup}\n"
            f"Destination: {ride.destination}\n"
            f"Stops: {stops_summary}\n"
            f"Distance: {ride.map.totalDistanceMeters/1000:.1f} km\n"
            f"Duration: {ride.map.totalDurationSeconds//60} mins\n"
            f"Vehicle: {ride.vehicleType}\n"
            f"User ID: {ride.userId}"
        )

        unit_amount = int(ride.price / 10)

        product_name = (
            f"Pickup: {ride.map.legs[0].startAddress}, Distance: {ride.map.totalDistanceMeters/1000:.1f} km"
        )

        payment_link = await run_in_threadpool(
            stripe.PaymentLink.create,
            line_items=[
                {
                    "price_data": {
                        "currency": "gbp",
                        "unit_amount": unit_amount,
                        "tax_behavior": "exclusive",
                        "product_data": {"name": product_name, "description": trip_description[:500]},
                    },
                    "quantity": 1,
                  
                }
            ],
            after_completion={"type": "redirect", "redirect": {"url": self.success_redirect_url}},
            metadata={"fare_id": ride.id, "user_id": ride.userId},
        )

        return payment_link.url

    async def generate_and_send_invoice(self, ride: RideOut) -> dict:
        from services.rider_service import retrieve_rider_by_rider_id

        if ride.paymentStatus:
            raise HTTPException(status_code=409, detail="Ride has already been paid.")

        rider: RiderOut = await retrieve_rider_by_rider_id(id=ride.userId)
        if not rider or not getattr(rider, "email", None):
            raise HTTPException(status_code=404, detail="Rider email not found.")

        amount = int(ride.price / 10)
        description = (
            f"Pickup: {ride.origin.address}\n"
            f"Distance: {ride.map.totalDistanceMeters / 1000:.1f} km\n"
            f"Duration: {ride.map.totalDurationSeconds // 60} mins\n"
        )

        customers = await run_in_threadpool(
            stripe.Customer.search,
            query=f"email:'{rider.email}'",
            limit=1,
        )

        if customers.data:
            customer = customers.data[0]
        else:
            customer = await run_in_threadpool(
                stripe.Customer.create,
                email=rider.email,
                name=f"{rider.firstName} {rider.lastName}".strip(),
                metadata={"rider_id": rider.id},
            )

        invoice = await run_in_threadpool(
            stripe.Invoice.create,
            customer=customer.id,
            auto_advance=True,
            collection_method="send_invoice",
            days_until_due=0,
            metadata={"ride_id": ride.id, "rider_id": rider.id},
        )

        await run_in_threadpool(
            stripe.InvoiceItem.create,
            customer=customer.id,
            invoice=invoice.id,
            amount=amount,
            tax_rates=[VAT_TAX_RATE_ID],
            currency="gbp",
            description=description,
            metadata={"ride_id": ride.id, "rider_id": rider.id},
        )

        finalized_invoice = await run_in_threadpool(stripe.Invoice.finalize_invoice, invoice.id)

        return {
            "invoice_id": finalized_invoice.id,
            "invoice_url": finalized_invoice.hosted_invoice_url,
            "status": finalized_invoice.status,
            "email_sent_to": rider.email,
        }

    async def refund_payment(self, payment_intent_id: str, amount: int = None) -> dict:
        try:
            refund_data = {"payment_intent": payment_intent_id}
            if amount:
                refund_data["amount"] = amount

            refund = await run_in_threadpool(stripe.Refund.create, **refund_data)

            return {"refund_id": refund.id, "status": refund.status}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))


class PaymentService:
    def __init__(self, provider: StripePaymentProvider):
        self.provider = provider

    async def create_payment_link(self, ride_id: str):
        from services.ride_service import retrieve_ride_by_ride_id

        ride = await retrieve_ride_by_ride_id(id=ride_id)
        return await self.provider.create_payment_link(ride)

    async def send_invoice(self, ride_id: str):
        from services.ride_service import retrieve_ride_by_ride_id

        ride = await retrieve_ride_by_ride_id(id=ride_id)
        return await self.provider.generate_and_send_invoice(ride)

    async def refund(self, payment_intent_id: str, amount: int = None):
        return await self.provider.refund_payment(payment_intent_id, amount)


def get_payment_service() -> PaymentService:
    stripe_provider = StripePaymentProvider(
        api_key=os.getenv("STRIPE_API_KEY"),
        success_redirect_url=os.getenv("FRONTEND_SUCCESS_URL"),
    )
    return PaymentService(provider=stripe_provider)
