import os
from dotenv import load_dotenv
from abc import ABC, abstractmethod
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
import stripe

from schemas.imports import CheckoutSessionObject, InvoiceData, RideStatus, StripeEvent
from schemas.ride import RideOut, RideUpdate
from schemas.rider_schema import RiderOut
from schemas.stripe_event import StripeEventCreate
from services.stripe_event_service import  retrieve_stripe_event_by_stripe_event_id

load_dotenv()

VAT_TAX_RATE_ID = os.getenv("STRIPE_TAX_RATE_ID")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")

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
    @abstractmethod
    async def handle_stripe_webhook(self,request: Request):
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
            metadata={"ride_id": ride.id, "user_id": ride.userId},
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
        
    async def handle_stripe_webhook(self, request: Request):
        """
        Stripe webhook handler supporting:
        - invoice.payment_succeeded
        - invoice.payment_failed
        - checkout.session.completed (Payment Links & Checkout)
        """

        from celery_worker import celery_app

        # 1) Verify Stripe signature
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        if not sig_header:
            return JSONResponse(status_code=400, content={"detail": "Missing Stripe signature"})

        try:
            event = stripe.webhooks.constructEvent(payload, sig_header, WEBHOOK_SECRET)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid payload"})
        except stripe.error.SignatureVerificationError:
            return JSONResponse(status_code=400, content={"detail": "Invalid signature"})

        stripe_event = StripeEvent(**event)
        event_id = stripe_event.id
        event_type = stripe_event.type
        data_obj = stripe_event.data["object"]
        
        stripe_event_create = StripeEventCreate(stripe_id=event_id,event=stripe_event)
        
        if await retrieve_stripe_event_by_stripe_event_id(event_id):
            return {"status": "ignored_duplicate"}
        
        
        celery_app.send_task("celery_worker.run_async_task",args=["add_stripe_event",{"payload": stripe_event_create.event.model_dump()}])
 
        
        



        # -----------------------------
        # HANDLE INVOICE EVENTS
        # -----------------------------
        if event_type == "invoice.payment_succeeded":
            invoice = InvoiceData(**data_obj)
            print(f"[WEBHOOK] Invoice paid: id={invoice.id}")

          
            ride_id = invoice.metadata.get("ride_id")
 
            invoiced_ride = RideUpdate(invoiceData=invoice,stripeEvent=stripe_event,paymentStatus=True)
            celery_app.send_task("celery_worker.run_async_task",args=["update_ride",{"ride_id":ride_id,"payload": invoiced_ride.event.model_dump()}])
             
            
        elif event_type == "invoice.payment_failed":
            invoice = InvoiceData(**data_obj)
            print(f"[WEBHOOK] Invoice payment failed: id={invoice.id}")

             

        # -----------------------------
        # HANDLE PAYMENT LINK / CHECKOUT
        # -----------------------------
        elif event_type == "checkout.session.completed":
            session = CheckoutSessionObject(**data_obj)

            # Only handle completed *paid* sessions
            if session.payment_status != "paid":
                return {"status": "ignored_not_paid"}

            # Payment Links always populate payment_link
            if not session.payment_link:
                return {"status": "ignored_not_payment_link"}

            print(f"[WEBHOOK] Checkout Session paid: id={session.id}")
 
            ride_id = session.metadata.get("ride_id")
            payment_intent_id = session.payment_intent

            paid_ride = RideUpdate(checkoutSessionObject=session,stripeEvent=stripe_event,rideStatus=RideStatus.findingDriver,payment_intent_id=payment_intent_id,paymentStatus=True)
            celery_app.send_task("celery_worker.run_async_task",args=["update_ride",{"ride_id":ride_id,"payload": paid_ride.event.model_dump()}])
             
   

        # -----------------------------
        # UNHANDLED EVENT TYPES
        # -----------------------------
        else:
            print(f"[WEBHOOK] Unhandled event type: {event_type}")

        return {"status": "success"}


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
    
    async def webhook_handler(self, request: Request):
        return await self.provider.handle_stripe_webhook(request=request)


def get_payment_service() -> PaymentService:
    stripe_provider = StripePaymentProvider(
        api_key=os.getenv("STRIPE_API_KEY"),
        success_redirect_url=os.getenv("FRONTEND_SUCCESS_URL"),
    )
    return PaymentService(provider=stripe_provider)
