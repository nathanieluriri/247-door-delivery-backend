import os
from abc import ABC, abstractmethod
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
import stripe

from schemas.driver import DriverOut, DriverUpdate
from schemas.stripe_event import StripeEventCreate
from services.stripe_event_service import retrieve_stripe_event_by_stripe_event_id
from dotenv import load_dotenv

load_dotenv()

# Environment variables for Stripe Connect
STRIPE_CONNECT_WEBHOOK_SECRET = os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET")
STRIPE_PLATFORM_FEE_PERCENT = float(os.getenv("STRIPE_PLATFORM_FEE_PERCENT", "0.1"))  # 10% platform fee


class StaffPaymentProvider(ABC):
    """Abstract base class for staff payment providers."""

    @abstractmethod
    async def create_connect_account(self, driver: DriverOut) -> dict:
        """Create a Stripe Connect Express account for a driver."""
        pass

    @abstractmethod
    async def generate_onboarding_link(self, stripe_account_id: str) -> str:
        """Generate a Stripe-hosted onboarding link for a driver."""
        pass

    @abstractmethod
    async def check_payout_eligibility(self, stripe_account_id: str) -> dict:
        """Check if a driver is eligible to receive payouts."""
        pass

    @abstractmethod
    async def create_transfer(self, stripe_account_id: str, amount: int, currency: str = "gbp",
                            description: str = None, metadata: dict = None) -> dict:
        """Transfer money from platform to driver's Stripe account."""
        pass

    @abstractmethod
    async def create_payout(self, stripe_account_id: str, amount: int, currency: str = "gbp") -> dict:
        """Create an instant payout to driver's bank account."""
        pass

    @abstractmethod
    async def handle_connect_webhook(self, request: Request) -> dict:
        """Handle Stripe Connect-specific webhook events."""
        pass


class StripeStaffPaymentProvider(StaffPaymentProvider):
    """
    Stripe Connect provider for paying drivers/staff.

    This class handles all Stripe Connect operations for driver payouts:
    - Creating Express accounts
    - Generating onboarding links
    - Checking payout eligibility
    - Transferring money to drivers
    - Handling Connect webhooks

    It does NOT handle customer payments, checkout, or invoices.
    """

    def __init__(self, api_key: str, refresh_url: str, return_url: str):
        """
        Initialize the Stripe Connect provider.

        Args:
            api_key: Stripe API key
            refresh_url: URL to redirect to if onboarding is refreshed
            return_url: URL to redirect to after successful onboarding
        """
        stripe.api_key = api_key
        self.refresh_url = refresh_url
        self.return_url = return_url

    async def create_connect_account(self, driver: DriverOut) -> dict:
        """
        Create a Stripe Connect Express account for a driver.

        Args:
            driver: Driver object with profile information

        Returns:
            dict: Contains stripe_account_id and account details

        Raises:
            HTTPException: If account creation fails
        """
        try:
            # Create Express account with minimal required info
            account = await run_in_threadpool(
                stripe.Account.create,
                type="express",
                country="GB",  # Default to UK, can be made configurable
                email=driver.email,
                capabilities={
                    "card_payments": {"requested": False},
                    "transfers": {"requested": True},
                },
                business_type="individual",  # Drivers are individuals
                metadata={
                    "driver_id": driver.id,
                    "platform": "door_delivery"
                }
            )

            return {
                "stripe_account_id": account.id,
                "account_status": account.details_submitted,
                "payouts_enabled": account.payouts_enabled,
                "requirements": account.requirements
            }

        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Failed to create Connect account: {str(e)}")

    async def generate_onboarding_link(self, stripe_account_id: str) -> str:
        """
        Generate a Stripe-hosted onboarding link for a driver.

        Args:
            stripe_account_id: The Stripe account ID

        Returns:
            str: The onboarding URL

        Raises:
            HTTPException: If link generation fails
        """
        try:
            account_link = await run_in_threadpool(
                stripe.AccountLink.create,
                account=stripe_account_id,
                refresh_url=self.refresh_url,
                return_url=self.return_url,
                type="account_onboarding",
            )

            return account_link.url

        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Failed to generate onboarding link: {str(e)}")

    async def check_payout_eligibility(self, stripe_account_id: str) -> dict:
        """
        Check if a driver is eligible to receive payouts.

        Args:
            stripe_account_id: The Stripe account ID

        Returns:
            dict: Eligibility status and requirements

        Raises:
            HTTPException: If account retrieval fails
        """
        try:
            account = await run_in_threadpool(
                stripe.Account.retrieve,
                stripe_account_id
            )

            return {
                "payouts_enabled": account.payouts_enabled,
                "details_submitted": account.details_submitted,
                "charges_enabled": account.charges_enabled,
                "requirements": {
                    "currently_due": account.requirements.currently_due,
                    "eventually_due": account.requirements.eventually_due,
                    "pending_verification": account.requirements.pending_verification
                }
            }

        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Failed to check payout eligibility: {str(e)}")

    async def create_transfer(self, stripe_account_id: str, amount: int, currency: str = "gbp",
                            description: str = None, metadata: dict = None) -> dict:
        """
        Transfer money from platform to driver's Stripe account.

        This creates a transfer that will be available in the driver's account balance.
        The driver can then initiate payouts from their dashboard.

        Args:
            stripe_account_id: The Stripe account ID to transfer to
            amount: Amount in smallest currency unit (pence for GBP)
            currency: Currency code (default: gbp)
            description: Transfer description
            metadata: Additional metadata

        Returns:
            dict: Transfer details

        Raises:
            HTTPException: If transfer fails
        """
        try:
            transfer_params = {
                "amount": amount,
                "currency": currency,
                "destination": stripe_account_id,
                "transfer_group": f"driver_payment_{stripe_account_id}_{amount}"
            }

            if description:
                transfer_params["description"] = description

            if metadata:
                transfer_params["metadata"] = metadata

            transfer = await run_in_threadpool(
                stripe.Transfer.create,
                **transfer_params
            )

            return {
                "transfer_id": transfer.id,
                "amount": transfer.amount,
                "currency": transfer.currency,
                "destination": transfer.destination,
                "status": "pending"  # Transfers are initially pending
            }

        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Failed to create transfer: {str(e)}")

    async def create_payout(self, stripe_account_id: str, amount: int, currency: str = "gbp") -> dict:
        """
        Create an instant payout to driver's bank account.

        This immediately sends money to the driver's bank account.
        Use sparingly as it incurs higher fees.

        Args:
            stripe_account_id: The Stripe account ID
            amount: Amount in smallest currency unit (pence for GBP)
            currency: Currency code (default: gbp)

        Returns:
            dict: Payout details

        Raises:
            HTTPException: If payout fails
        """
        try:
            payout = await run_in_threadpool(
                stripe.Payout.create,
                amount=amount,
                currency=currency,
                stripe_account=stripe_account_id,
                method="instant",  # Instant payout to bank
                metadata={
                    "driver_account": stripe_account_id,
                    "payout_type": "instant"
                }
            )

            return {
                "payout_id": payout.id,
                "amount": payout.amount,
                "currency": payout.currency,
                "status": payout.status,
                "arrival_date": payout.arrival_date
            }

        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=f"Failed to create payout: {str(e)}")

    async def handle_connect_webhook(self, request: Request) -> dict:
        """
        Handle Stripe Connect-specific webhook events.

        Processes events like:
        - account.updated: Account status changes
        - account.application.deauthorized: Driver disconnected account

        Args:
            request: The webhook request

        Returns:
            dict: Processing status

        Raises:
            HTTPException: If webhook processing fails
        """
        from celery_worker import celery_app

        # Verify Stripe signature
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            return JSONResponse(status_code=400, content={"detail": "Missing Stripe signature"})

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_CONNECT_WEBHOOK_SECRET)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid payload"})
        except stripe.error.SignatureVerificationError:
            return JSONResponse(status_code=400, content={"detail": "Invalid signature"})

        # Check for duplicate events
        event_id = event["id"]
        if await retrieve_stripe_event_by_stripe_event_id(event_id):
            return {"status": "ignored_duplicate"}

        # Store the event
        stripe_event_create = StripeEventCreate(stripe_id=event_id, event=event)
        celery_app.send_task(
            "celery_worker.run_async_task",
            args=["add_stripe_event", {"payload": stripe_event_create.model_dump()}]
        )

        event_type = event["type"]
        account_id = event["data"]["object"]["id"]

        # Handle Connect-specific events
        if event_type == "account.updated":
            # Update driver's payout eligibility in our system
            account_data = event["data"]["object"]

            driver_update = DriverUpdate(
                stripeAccountId=account_id,
                payoutsEnabled=account_data.get("payouts_enabled", False),
                detailsSubmitted=account_data.get("details_submitted", False)
            )

            # Find driver by stripe account ID and update
            from services.driver_service import update_driver_by_stripe_account_id
            await update_driver_by_stripe_account_id(account_id, driver_update)

            print(f"[CONNECT WEBHOOK] Account updated: {account_id}")

        elif event_type == "account.application.deauthorized":
            # Driver disconnected their Stripe account
            driver_update = DriverUpdate(
                stripeAccountId=None,  # Clear the account ID
                payoutsEnabled=False,
                detailsSubmitted=False
            )

            from services.driver_service import update_driver_by_stripe_account_id
            await update_driver_by_stripe_account_id(account_id, driver_update)

            print(f"[CONNECT WEBHOOK] Account deauthorized: {account_id}")

        else:
            print(f"[CONNECT WEBHOOK] Unhandled event type: {event_type}")

        return {"status": "success"}


class StaffPaymentService:
    """
    Service layer for staff payments.

    Provides high-level methods for driver payment operations.
    """

    def __init__(self, provider: StripeStaffPaymentProvider):
        self.provider = provider

    async def onboard_driver(self, driver: DriverOut) -> dict:
        """
        Complete driver onboarding flow.

        1. Create Connect account if not exists
        2. Generate onboarding link
        3. Return link for driver to complete onboarding

        Args:
            driver: Driver object

        Returns:
            dict: Onboarding information
        """
        # Check if driver already has a Connect account
        if not hasattr(driver, 'stripeAccountId') or not driver.stripeAccountId:
            # Create new account
            account_result = await self.provider.create_connect_account(driver)

            # Update driver with stripe account ID
            driver_update = DriverUpdate(stripeAccountId=account_result["stripe_account_id"])
            from services.driver_service import update_driver_by_id
            await update_driver_by_id(driver.id, driver_update)

            stripe_account_id = account_result["stripe_account_id"]
        else:
            stripe_account_id = driver.stripeAccountId

        # Generate onboarding link
        onboarding_url = await self.provider.generate_onboarding_link(stripe_account_id)

        # Check current eligibility
        eligibility = await self.provider.check_payout_eligibility(stripe_account_id)

        return {
            "stripe_account_id": stripe_account_id,
            "onboarding_url": onboarding_url,
            "eligibility": eligibility
        }

    async def pay_driver(self, driver: DriverOut, amount: int, description: str = None,
                        instant: bool = False) -> dict:
        """
        Pay a driver for completed work.

        Args:
            driver: Driver object
            amount: Amount to pay in pence
            description: Payment description
            instant: Whether to do instant payout (higher fees)

        Returns:
            dict: Payment result

        Raises:
            HTTPException: If payment fails or driver ineligible
        """
        if not driver.stripeAccountId:
            raise HTTPException(status_code=400, detail="Driver has no Stripe Connect account")

        # Check payout eligibility
        eligibility = await self.provider.check_payout_eligibility(driver.stripeAccountId)
        if not eligibility["payouts_enabled"]:
            raise HTTPException(status_code=400, detail="Driver is not eligible for payouts")

        # Calculate platform fee and driver amount
        platform_fee = int(amount * STRIPE_PLATFORM_FEE_PERCENT)
        driver_amount = amount - platform_fee

        metadata = {
            "driver_id": driver.id,
            "ride_payment": True,
            "platform_fee": platform_fee
        }

        if instant:
            # Instant payout (higher fees, immediate to bank)
            result = await self.provider.create_payout(
                driver.stripeAccountId,
                driver_amount,
                description=description,
                metadata=metadata
            )
        else:
            # Transfer to account balance (driver controls payout timing)
            result = await self.provider.create_transfer(
                driver.stripeAccountId,
                driver_amount,
                description=description,
                metadata=metadata
            )

        return {
            "payment_id": result.get("transfer_id") or result.get("payout_id"),
            "amount_paid": driver_amount,
            "platform_fee": platform_fee,
            "payment_type": "instant_payout" if instant else "transfer",
            "status": result.get("status", "pending")
        }

    async def get_driver_payment_status(self, driver: DriverOut) -> dict:
        """
        Get a driver's current payment status and eligibility.

        Args:
            driver: Driver object

        Returns:
            dict: Payment status information
        """
        if not driver.stripeAccountId:
            return {
                "has_account": False,
                "eligible_for_payment": False,
                "needs_onboarding": True
            }

        eligibility = await self.provider.check_payout_eligibility(driver.stripeAccountId)

        return {
            "has_account": True,
            "stripe_account_id": driver.stripeAccountId,
            "eligible_for_payment": eligibility["payouts_enabled"],
            "details_submitted": eligibility["details_submitted"],
            "requirements": eligibility["requirements"]
        }

    async def handle_webhook(self, request: Request) -> dict:
        """Handle Stripe Connect webhooks."""
        return await self.provider.handle_connect_webhook(request)


def get_staff_payment_service() -> StaffPaymentService:
    """
    Factory function to create the staff payment service.

    Returns:
        StaffPaymentService: Configured service instance
    """
    stripe_provider = StripeStaffPaymentProvider(
        api_key=os.getenv("STRIPE_API_KEY"),
        refresh_url=os.getenv("STRIPE_CONNECT_REFRESH_URL"),
        return_url=os.getenv("STRIPE_CONNECT_RETURN_URL"),
    )
    return StaffPaymentService(provider=stripe_provider)
