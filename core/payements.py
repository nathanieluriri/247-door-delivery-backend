# core/payments.py
import os
from dotenv import load_dotenv
from fastapi import HTTPException
from abc import ABC, abstractmethod
from schemas.ride import RideOut

import stripe
from fastapi import HTTPException
class PaymentProvider(ABC):

    @abstractmethod
    async def create_payment_link(self, ride: RideOut) -> dict:
        """Create a payment link for this ride."""
        pass
 


class StripePaymentProvider(PaymentProvider):

    def __init__(self, api_key: str, success_redirect_url: str):
        stripe.api_key = api_key
        self.success_redirect_url = success_redirect_url

    async def create_payment_link(self, ride: RideOut) -> dict:

        if ride.paymentStatus:
            raise HTTPException(
                status_code=409,
                detail="Fare has already been paid."
            )

        # Description
        stops_summary = " → ".join(ride.stops) if ride.stops else "No stops"
        description = (
            f"Pickup: {ride.pickup}\n"
            f"Destination: {ride.destination}\n"
            f"Stops: {stops_summary}\n"
            f"Distance: {ride.map.totalDistanceMeters/1000:.1f} km\n"
            f"Duration: {ride.map.totalDurationSeconds//60} mins\n"
            f"Vehicle: {ride.vehicleType}\n"
            f"User ID: {ride.userId}"
        )

        unit_amount = int(ride.price / 10)

        # Create price object
        price = stripe.Price.create(
            currency="GBP",
            unit_amount=unit_amount,
            product_data={"name": f"Pickup: {ride.map.legs[0].startAddress},\n Distance: {ride.map.totalDistanceMeters/1000:.1f} km\n, Duration of ride: {ride.map.totalDurationSeconds//60} mins\n Dropoff: {ride.map.legs[0].endAddress},\n" },
            metadata={
                "fare_id": ride.id,
                "user_id": ride.userId,
                "trip_description": description,
            }
        )

        payment_link = stripe.PaymentLink.create(
            line_items=[{"price": price.id, "quantity": 1}],
            after_completion={
                "type": "redirect",
                "redirect": {"url": self.success_redirect_url},
            },
            metadata={"fare_id": ride.id, "user_id": ride.userId}
        )

        return payment_link.url


class PaymentService:

    def __init__(self, provider: StripePaymentProvider):
        self.provider = provider

    async def create_payment_link(self, ride_id: str):
        try:
            from services.ride_service import retrieve_ride_by_ride_id
            ride = await retrieve_ride_by_ride_id(id=ride_id)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve ride: {e}"
            )

        return await self.provider.create_payment_link(ride)



load_dotenv()

def get_payment_service() -> PaymentService:
    stripe_provider = StripePaymentProvider(
        api_key=os.getenv("STRIPE_API_KEY"),
        success_redirect_url=os.getenv("FRONTEND_SUCCESS_URL")
    )

    return PaymentService(provider=stripe_provider)