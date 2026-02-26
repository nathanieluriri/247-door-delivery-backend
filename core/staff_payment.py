import os
import time
from abc import ABC, abstractmethod
from typing import Any, Optional
from urllib.parse import urlencode

try:
    import stripe
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal fake-only environments
    stripe = None
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from repositories.driver_onboarding_repo import (
    complete_driver_onboarding,
    get_driver_onboarding_profile,
    get_driver_onboarding_profile_by_account_id,
    upsert_driver_onboarding_draft,
)
from schemas.driver import DriverOut, DriverUpdate, DriverUpdateStripeAccountId
from schemas.driver_onboarding import FakeOnboardingDraftIn
from schemas.imports import AccountStatus
from schemas.stripe_event import StripeEventCreate
from security.oauth_return import resolve_return_url_or_raise
from services.stripe_event_service import retrieve_stripe_event_by_stripe_event_id

# Environment variables for Stripe Connect
STRIPE_CONNECT_WEBHOOK_SECRET = os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET")
STRIPE_PLATFORM_FEE_PERCENT = float(os.getenv("STRIPE_PLATFORM_FEE_PERCENT", "0.1"))  # 10% platform fee
_SUPPORTED_STAFF_PROVIDERS = {"stripe", "fake"}


class StaffPaymentProvider(ABC):
    """Abstract base class for staff payment providers."""

    provider_name: str

    @abstractmethod
    async def create_connect_account(self, driver: DriverOut) -> dict:
        """Create a payout account for a driver."""

    @abstractmethod
    async def generate_onboarding_link(self, stripe_account_id: str) -> str:
        """Generate a hosted onboarding link for a driver."""

    @abstractmethod
    async def check_payout_eligibility(self, stripe_account_id: str) -> dict:
        """Check if a driver is eligible to receive payouts."""

    @abstractmethod
    async def create_transfer(
        self,
        stripe_account_id: str,
        amount: int,
        currency: str = "gbp",
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Transfer money from platform to driver's payout account."""

    @abstractmethod
    async def create_payout(
        self,
        stripe_account_id: str,
        amount: int,
        currency: str = "gbp",
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Create an instant payout to driver's bank account."""

    @abstractmethod
    async def handle_connect_webhook(self, request: Request) -> dict:
        """Handle provider-specific payout webhook events."""


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

    provider_name = "stripe"

    def __init__(self, api_key: str, refresh_url: str, return_url: str):
        """
        Initialize the Stripe Connect provider.

        Args:
            api_key: Stripe API key
            refresh_url: URL to redirect to if onboarding is refreshed
            return_url: URL to redirect to after successful onboarding
        """
        if stripe is None:
            raise RuntimeError("stripe package is required for staff payment provider 'stripe'")
        if not api_key:
            raise RuntimeError("STRIPE_API_KEY is required for staff payment provider 'stripe'")
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
                    "platform": "door_delivery",
                },
            )

            return {
                "stripe_account_id": account.id,
                "account_status": account.details_submitted,
                "payouts_enabled": account.payouts_enabled,
                "requirements": account.requirements,
            }

        except stripe.error.StripeError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create Connect account: {str(err)}",
            ) from err

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

        except stripe.error.StripeError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to generate onboarding link: {str(err)}",
            ) from err

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
                stripe_account_id,
            )

            return {
                "payouts_enabled": account.payouts_enabled,
                "details_submitted": account.details_submitted,
                "charges_enabled": account.charges_enabled,
                "requirements": {
                    "currently_due": account.requirements.currently_due,
                    "eventually_due": account.requirements.eventually_due,
                    "pending_verification": account.requirements.pending_verification,
                },
            }

        except stripe.error.StripeError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to check payout eligibility: {str(err)}",
            ) from err

    async def create_transfer(
        self,
        stripe_account_id: str,
        amount: int,
        currency: str = "gbp",
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
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
                "transfer_group": f"driver_payment_{stripe_account_id}_{amount}",
            }

            if description:
                transfer_params["description"] = description

            if metadata:
                transfer_params["metadata"] = metadata

            idempotency_key = f"transfer:{stripe_account_id}:{amount}:{description or ''}"
            transfer = await run_in_threadpool(
                stripe.Transfer.create,
                **transfer_params,
                idempotency_key=idempotency_key,
            )

            return {
                "transfer_id": transfer.id,
                "amount": transfer.amount,
                "currency": transfer.currency,
                "destination": transfer.destination,
                "status": "pending",  # Transfers are initially pending
            }

        except stripe.error.StripeError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create transfer: {str(err)}",
            ) from err

    async def create_payout(
        self,
        stripe_account_id: str,
        amount: int,
        currency: str = "gbp",
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
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
            payout_metadata = {
                "driver_account": stripe_account_id,
                "payout_type": "instant",
            }
            if metadata:
                payout_metadata.update(metadata)

            idempotency_key = f"payout:{stripe_account_id}:{amount}:{description or ''}"
            payout = await run_in_threadpool(
                stripe.Payout.create,
                amount=amount,
                currency=currency,
                stripe_account=stripe_account_id,
                method="instant",  # Instant payout to bank
                description=description,
                metadata=payout_metadata,
                idempotency_key=idempotency_key,
            )

            return {
                "payout_id": payout.id,
                "amount": payout.amount,
                "currency": payout.currency,
                "status": payout.status,
                "arrival_date": payout.arrival_date,
            }

        except stripe.error.StripeError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create payout: {str(err)}",
            ) from err

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
            args=["add_stripe_event", {"payload": stripe_event_create.model_dump()}],
        )

        event_type = event["type"]
        account_id = event["data"]["object"]["id"]

        # Handle Connect-specific events
        if event_type == "account.updated":
            # Update driver's payout eligibility in our system
            account_data = event["data"]["object"]

            requirements = account_data.get("requirements", {}) or {}
            currently_due = requirements.get("currently_due")
            is_onboarding_complete = (
                account_data.get("details_submitted") is True
                and account_data.get("payouts_enabled") is True
                and (not currently_due)
            )
            driver_update = DriverUpdate(
                stripeAccountId=account_id,
                payoutsEnabled=account_data.get("payouts_enabled", False),
                chargesEnabled=account_data.get("charges_enabled", False),
                detailsSubmitted=account_data.get("details_submitted", False),
                requirementsCurrentlyDue=currently_due,
                requirementsEventuallyDue=requirements.get("eventually_due"),
                requirementsPendingVerification=requirements.get("pending_verification"),
                accountStatus=AccountStatus.ACTIVE if is_onboarding_complete else None,
            )

            # Find driver by stripe account ID and update
            from services.driver_service import update_driver_by_stripe_account_id

            await update_driver_by_stripe_account_id(account_id, driver_update)

        elif event_type == "account.application.deauthorized":
            # Driver disconnected their Stripe account
            driver_update = DriverUpdate(
                stripeAccountId=None,  # Clear the account ID
                payoutsEnabled=False,
                chargesEnabled=False,
                detailsSubmitted=False,
                requirementsCurrentlyDue=None,
                requirementsEventuallyDue=None,
                requirementsPendingVerification=None,
            )

            from services.driver_service import update_driver_by_stripe_account_id

            await update_driver_by_stripe_account_id(account_id, driver_update)

        return {"status": "success"}


class FakeStaffPaymentProvider(StaffPaymentProvider):
    """In-app fake payout provider for local/staging testing flows."""

    provider_name = "fake"

    def __init__(self, base_url: str):
        if not base_url:
            raise RuntimeError("FAKE_PAYMENT_BASE_URL is required for staff payment provider 'fake'")
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def _fake_account_id(driver_id: str) -> str:
        safe_tail = "".join(ch for ch in (driver_id or "") if ch.isalnum())[-24:]
        if not safe_tail:
            safe_tail = str(int(time.time()))
        return f"acct_fake_{safe_tail}"

    async def create_connect_account(self, driver: DriverOut) -> dict:
        account_id = self._fake_account_id(driver.id or "")
        return {
            "stripe_account_id": account_id,
            "account_status": False,
            "payouts_enabled": False,
            "requirements": {"currently_due": ["onboarding_form"], "eventually_due": []},
        }

    async def generate_onboarding_link(self, stripe_account_id: str) -> str:
        return f"{self.base_url}/api/web/payouts/fake/onboarding?account_id={stripe_account_id}"

    async def check_payout_eligibility(self, stripe_account_id: str) -> dict:
        profile = await get_driver_onboarding_profile_by_account_id(
            account_id=stripe_account_id,
            provider="fake",
        )
        is_complete = bool(profile and profile.get("status") == "completed")
        currently_due = [] if is_complete else ["onboarding_form"]
        return {
            "payouts_enabled": is_complete,
            "details_submitted": is_complete,
            "charges_enabled": is_complete,
            "requirements": {
                "currently_due": currently_due,
                "eventually_due": [],
                "pending_verification": [],
            },
        }

    async def create_transfer(
        self,
        stripe_account_id: str,
        amount: int,
        currency: str = "gbp",
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        return {
            "transfer_id": f"tr_fake_{int(time.time() * 1000)}",
            "amount": amount,
            "currency": currency,
            "destination": stripe_account_id,
            "status": "pending",
            "description": description,
            "metadata": metadata or {},
        }

    async def create_payout(
        self,
        stripe_account_id: str,
        amount: int,
        currency: str = "gbp",
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        return {
            "payout_id": f"po_fake_{int(time.time() * 1000)}",
            "amount": amount,
            "currency": currency,
            "status": "paid",
            "arrival_date": int(time.time()),
            "description": description,
            "metadata": metadata or {},
            "destination": stripe_account_id,
        }

    async def handle_connect_webhook(self, request: Request) -> dict:
        _ = request
        return {"status": "ignored", "provider": "fake"}


class StaffPaymentService:
    """
    Service layer for staff payments.

    Provides high-level methods for driver payment operations.
    """

    def __init__(self, provider: StaffPaymentProvider):
        self.provider = provider

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    @staticmethod
    def _deep_merge(current: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = dict(current)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = StaffPaymentService._deep_merge(merged[key], value)
                continue
            merged[key] = value
        return merged

    @staticmethod
    def _required_fields_from_draft(draft: dict[str, Any]) -> list[str]:
        required_paths = [
            ("personal", "first_name"),
            ("personal", "last_name"),
            ("personal", "email"),
            ("personal", "phone"),
            ("personal", "dob_day"),
            ("personal", "dob_month"),
            ("personal", "dob_year"),
            ("address", "line1"),
            ("address", "city"),
            ("address", "postal_code"),
            ("address", "country"),
            ("bank", "account_holder_name"),
            ("bank", "account_number"),
            ("bank", "sort_code"),
            ("attestations", "tos_accepted"),
            ("attestations", "identity_confirmed"),
            ("attestations", "information_accurate"),
        ]

        missing: list[str] = []
        for section, field in required_paths:
            section_data = draft.get(section)
            if not isinstance(section_data, dict):
                missing.append(f"{section}.{field}")
                continue
            value = section_data.get(field)
            if value is None:
                missing.append(f"{section}.{field}")
                continue
            if isinstance(value, str) and not value.strip():
                missing.append(f"{section}.{field}")
                continue
            if field in {"tos_accepted", "identity_confirmed", "information_accurate"} and value is not True:
                missing.append(f"{section}.{field}")

        return missing

    def _resolve_return_url(self, backend_host: str | None, requested_return_url: str | None) -> str:
        host = backend_host or "localhost"
        return resolve_return_url_or_raise(
            role="driver",
            backend_host=host,
            next_url=requested_return_url,
        )

    def _build_fake_onboarding_url(
        self,
        *,
        account_id: str,
        driver_access_token: str | None,
        return_url: str,
    ) -> str:
        if not isinstance(self.provider, FakeStaffPaymentProvider):
            raise RuntimeError("Fake onboarding URL requested for non-fake provider")
        query = {
            "account_id": account_id,
            "return_url": return_url,
        }
        if driver_access_token:
            query["token"] = driver_access_token
        return f"{self.provider.base_url}/api/web/payouts/fake/onboarding?{urlencode(query)}"

    def _build_fake_status_payload(self, profile: dict[str, Any], account_id: str) -> dict[str, Any]:
        status_value = str(profile.get("status") or "not_started")
        draft = profile.get("draft") or {}
        required_missing = [] if status_value == "completed" else self._required_fields_from_draft(draft)
        return {
            "provider": "fake",
            "account_id": account_id,
            "status": status_value,
            "draft": draft,
            "completion": profile.get("completion"),
            "required_missing": required_missing,
            "return_url": profile.get("return_url"),
            "created_at": profile.get("created_at"),
            "updated_at": profile.get("updated_at"),
            "completed_at": profile.get("completed_at"),
        }

    async def onboard_driver(
        self,
        driver: DriverOut,
        *,
        driver_access_token: str | None = None,
        requested_return_url: str | None = None,
        backend_host: str | None = None,
    ) -> dict:
        """
        Complete driver onboarding flow.

        1. Create payout account if not exists
        2. Generate onboarding link
        3. Return link for driver to complete onboarding

        Args:
            driver: Driver object

        Returns:
            dict: Onboarding information
        """
        # Check if driver already has a payout account
        if not hasattr(driver, "stripeAccountId") or not driver.stripeAccountId:
            # Create new account
            account_result = await self.provider.create_connect_account(driver)

            # Update driver with account ID
            driver_update = DriverUpdateStripeAccountId(stripeAccountId=account_result["stripe_account_id"])
            from services.driver_service import update_driver_by_id

            await update_driver_by_id(driver.id, driver_update)

            stripe_account_id = account_result["stripe_account_id"]
        else:
            stripe_account_id = driver.stripeAccountId

        if self.provider_name == "fake":
            resolved_return_url = self._resolve_return_url(backend_host, requested_return_url)
            profile = await upsert_driver_onboarding_draft(
                driver_id=driver.id,
                provider="fake",
                account_id=stripe_account_id,
                return_url=resolved_return_url,
            )
            onboarding_url = self._build_fake_onboarding_url(
                account_id=stripe_account_id,
                driver_access_token=driver_access_token,
                return_url=resolved_return_url,
            )
            eligibility = await self.provider.check_payout_eligibility(stripe_account_id)

            requirements = eligibility.get("requirements", {}) or {}
            currently_due = requirements.get("currently_due")
            is_onboarding_complete = (
                eligibility.get("details_submitted") is True
                and eligibility.get("payouts_enabled") is True
                and (not currently_due)
            )
            driver_update = DriverUpdate(
                stripeAccountId=stripe_account_id,
                payoutsEnabled=eligibility.get("payouts_enabled"),
                chargesEnabled=eligibility.get("charges_enabled"),
                detailsSubmitted=eligibility.get("details_submitted"),
                requirementsCurrentlyDue=currently_due,
                requirementsEventuallyDue=requirements.get("eventually_due"),
                requirementsPendingVerification=requirements.get("pending_verification"),
                onboardingRefreshUrl=onboarding_url,
                onboardingReturnUrl=resolved_return_url,
                accountStatus=AccountStatus.ACTIVE if is_onboarding_complete else None,
            )
            from services.driver_service import update_driver_by_id

            await update_driver_by_id(driver.id, driver_update)

            return {
                "provider": "fake",
                "stripe_account_id": stripe_account_id,
                "onboarding_url": onboarding_url,
                "eligibility": eligibility,
                "status": profile.get("status") or "in_progress",
                "return_url": resolved_return_url,
            }

        # Generate onboarding link
        onboarding_url = await self.provider.generate_onboarding_link(stripe_account_id)

        # Check current eligibility
        eligibility = await self.provider.check_payout_eligibility(stripe_account_id)

        # Persist Stripe onboarding + eligibility snapshot on driver
        requirements = eligibility.get("requirements", {}) or {}
        currently_due = requirements.get("currently_due")
        is_onboarding_complete = (
            eligibility.get("details_submitted") is True
            and eligibility.get("payouts_enabled") is True
            and (not currently_due)
        )
        if isinstance(self.provider, StripeStaffPaymentProvider):
            onboarding_refresh_url = self.provider.refresh_url
            onboarding_return_url = self.provider.return_url
        else:
            onboarding_refresh_url = None
            onboarding_return_url = None

        driver_update = DriverUpdate(
            stripeAccountId=stripe_account_id,
            payoutsEnabled=eligibility.get("payouts_enabled"),
            chargesEnabled=eligibility.get("charges_enabled"),
            detailsSubmitted=eligibility.get("details_submitted"),
            requirementsCurrentlyDue=currently_due,
            requirementsEventuallyDue=requirements.get("eventually_due"),
            requirementsPendingVerification=requirements.get("pending_verification"),
            onboardingRefreshUrl=onboarding_refresh_url,
            onboardingReturnUrl=onboarding_return_url,
            accountStatus=AccountStatus.ACTIVE if is_onboarding_complete else None,
        )
        from services.driver_service import update_driver_by_id

        await update_driver_by_id(driver.id, driver_update)

        return {
            "provider": "stripe",
            "stripe_account_id": stripe_account_id,
            "onboarding_url": onboarding_url,
            "eligibility": eligibility,
        }

    async def get_fake_onboarding_state(
        self,
        driver: DriverOut,
        *,
        requested_return_url: str | None = None,
        backend_host: str | None = None,
    ) -> dict[str, Any]:
        if self.provider_name != "fake":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fake onboarding endpoints are only available when fake payout provider is enabled",
            )

        account_id = driver.stripeAccountId
        if not account_id:
            account_result = await self.provider.create_connect_account(driver)
            account_id = account_result["stripe_account_id"]
            from services.driver_service import update_driver_by_id

            await update_driver_by_id(
                driver.id,
                DriverUpdateStripeAccountId(stripeAccountId=account_id),
            )

        return_url = (
            self._resolve_return_url(backend_host, requested_return_url)
            if requested_return_url is not None
            else None
        )

        if return_url is not None:
            profile = await upsert_driver_onboarding_draft(
                driver_id=driver.id,
                provider="fake",
                account_id=account_id,
                return_url=return_url,
            )
        else:
            profile = await get_driver_onboarding_profile(driver.id, provider="fake")
            if profile is None:
                resolved_default = self._resolve_return_url(backend_host, None)
                profile = await upsert_driver_onboarding_draft(
                    driver_id=driver.id,
                    provider="fake",
                    account_id=account_id,
                    return_url=resolved_default,
                )

        return self._build_fake_status_payload(profile, account_id)

    async def save_fake_onboarding(
        self,
        driver: DriverOut,
        payload: FakeOnboardingDraftIn,
        *,
        requested_return_url: str | None = None,
        backend_host: str | None = None,
    ) -> dict[str, Any]:
        if self.provider_name != "fake":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fake onboarding endpoints are only available when fake payout provider is enabled",
            )

        account_id = driver.stripeAccountId
        if not account_id:
            account_result = await self.provider.create_connect_account(driver)
            account_id = account_result["stripe_account_id"]
            from services.driver_service import update_driver_by_id

            await update_driver_by_id(
                driver.id,
                DriverUpdateStripeAccountId(stripeAccountId=account_id),
            )

        existing = await get_driver_onboarding_profile(driver.id, provider="fake")
        if existing and existing.get("status") == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Onboarding has already been completed",
            )

        payload_dict = payload.model_dump(exclude_none=True)
        payload_return_url = payload_dict.pop("return_url", None)
        effective_return_url = payload_return_url if payload_return_url is not None else requested_return_url
        resolved_return_url = (
            self._resolve_return_url(backend_host, effective_return_url)
            if effective_return_url is not None
            else None
        )

        profile = await upsert_driver_onboarding_draft(
            driver_id=driver.id,
            provider="fake",
            account_id=account_id,
            draft_updates=payload_dict,
            return_url=resolved_return_url,
        )

        return self._build_fake_status_payload(profile, account_id)

    async def complete_fake_onboarding(
        self,
        driver: DriverOut,
        payload: FakeOnboardingDraftIn,
        *,
        requested_return_url: str | None = None,
        backend_host: str | None = None,
    ) -> dict[str, Any]:
        if self.provider_name != "fake":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fake onboarding endpoints are only available when fake payout provider is enabled",
            )

        account_id = driver.stripeAccountId
        if not account_id:
            account_result = await self.provider.create_connect_account(driver)
            account_id = account_result["stripe_account_id"]
            from services.driver_service import update_driver_by_id

            await update_driver_by_id(
                driver.id,
                DriverUpdateStripeAccountId(stripeAccountId=account_id),
            )

        existing = await get_driver_onboarding_profile(driver.id, provider="fake")
        existing_draft = (existing or {}).get("draft") or {}

        payload_dict = payload.model_dump(exclude_none=True)
        payload_return_url = payload_dict.pop("return_url", None)

        merged_draft = self._deep_merge(existing_draft, payload_dict)
        missing_fields = self._required_fields_from_draft(merged_draft)
        if missing_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Onboarding form is incomplete",
                    "required_missing": missing_fields,
                },
            )

        effective_return_url = payload_return_url
        if effective_return_url is None:
            effective_return_url = requested_return_url
        if effective_return_url is None and existing:
            effective_return_url = existing.get("return_url")

        resolved_return_url = self._resolve_return_url(backend_host, effective_return_url)

        now = int(time.time())
        completion_payload = {
            "submitted_at": now,
            "verified": True,
            "provider": "fake",
            "account_id": account_id,
        }

        completed_profile = await complete_driver_onboarding(
            driver_id=driver.id,
            provider="fake",
            account_id=account_id,
            completion=completion_payload,
            draft_updates=merged_draft,
            return_url=resolved_return_url,
        )

        eligibility = await self.provider.check_payout_eligibility(account_id)
        requirements = eligibility.get("requirements", {}) or {}
        driver_update = DriverUpdate(
            stripeAccountId=account_id,
            payoutsEnabled=eligibility.get("payouts_enabled"),
            chargesEnabled=eligibility.get("charges_enabled"),
            detailsSubmitted=eligibility.get("details_submitted"),
            requirementsCurrentlyDue=requirements.get("currently_due"),
            requirementsEventuallyDue=requirements.get("eventually_due"),
            requirementsPendingVerification=requirements.get("pending_verification"),
            onboardingReturnUrl=resolved_return_url,
            accountStatus=AccountStatus.ACTIVE,
        )
        from services.driver_service import update_driver_by_id

        await update_driver_by_id(driver.id, driver_update)

        return {
            "provider": "fake",
            "account_id": account_id,
            "status": "completed",
            "redirect_url": resolved_return_url,
            "completed_at": completed_profile.get("completed_at") or now,
        }

    async def pay_driver(
        self,
        driver: DriverOut,
        amount: int,
        description: Optional[str] = None,
        instant: bool = False,
    ) -> dict:
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
            raise HTTPException(status_code=400, detail="Driver has no payout account")

        # Check payout eligibility
        eligibility = await self.provider.check_payout_eligibility(driver.stripeAccountId)
        if not eligibility["payouts_enabled"]:
            raise HTTPException(status_code=400, detail="Driver is not eligible for payouts")

        # Calculate platform fee and driver amount
        platform_fee = int(round(amount * STRIPE_PLATFORM_FEE_PERCENT))
        driver_amount = amount - platform_fee

        metadata = {
            "driver_id": driver.id,
            "ride_payment": True,
            "platform_fee": platform_fee,
            "provider": self.provider_name,
        }

        if instant:
            # Instant payout (higher fees, immediate to bank)
            result = await self.provider.create_payout(
                driver.stripeAccountId,
                driver_amount,
                description=description,
                metadata=metadata,
            )
        else:
            # Transfer to account balance (driver controls payout timing)
            result = await self.provider.create_transfer(
                driver.stripeAccountId,
                driver_amount,
                description=description,
                metadata=metadata,
            )

        return {
            "provider": self.provider_name,
            "payment_id": result.get("transfer_id") or result.get("payout_id"),
            "amount_paid": driver_amount,
            "platform_fee": platform_fee,
            "payment_type": "instant_payout" if instant else "transfer",
            "status": result.get("status", "pending"),
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
                "provider": self.provider_name,
                "has_account": False,
                "eligible_for_payment": False,
                "needs_onboarding": True,
            }

        eligibility = await self.provider.check_payout_eligibility(driver.stripeAccountId)

        response = {
            "provider": self.provider_name,
            "has_account": True,
            "stripe_account_id": driver.stripeAccountId,
            "eligible_for_payment": eligibility["payouts_enabled"],
            "details_submitted": eligibility["details_submitted"],
            "requirements": eligibility["requirements"],
        }

        if self.provider_name == "fake":
            profile = await get_driver_onboarding_profile(driver.id, provider="fake")
            response["fake_onboarding_status"] = (profile or {}).get("status") or "not_started"

        return response

    async def handle_webhook(self, request: Request) -> dict:
        """Handle payout webhooks."""
        return await self.provider.handle_connect_webhook(request)


def get_staff_payment_service() -> StaffPaymentService:
    """
    Factory function to create the staff payment service.

    Provider is selected strictly from env and must be configured.

    Returns:
        StaffPaymentService: Configured service instance
    """
    configured_provider = (
        os.getenv("STAFF_PAYMENT_DEFAULT_PROVIDER")
        or os.getenv("PAYMENT_DEFAULT_PROVIDER")
        or "stripe"
    ).strip().lower()

    if configured_provider not in _SUPPORTED_STAFF_PROVIDERS:
        raise RuntimeError(
            "Unsupported staff payment provider "
            f"'{configured_provider}'. Supported values: {sorted(_SUPPORTED_STAFF_PROVIDERS)}"
        )

    if configured_provider == "stripe":
        stripe_provider = StripeStaffPaymentProvider(
            api_key=(os.getenv("STRIPE_API_KEY") or "").strip(),
            refresh_url=(os.getenv("STRIPE_CONNECT_REFRESH_URL") or "").strip(),
            return_url=(os.getenv("STRIPE_CONNECT_RETURN_URL") or "").strip(),
        )
        return StaffPaymentService(provider=stripe_provider)

    fake_provider = FakeStaffPaymentProvider(
        base_url=(os.getenv("FAKE_PAYMENT_BASE_URL") or "").strip(),
    )
    return StaffPaymentService(provider=fake_provider)
