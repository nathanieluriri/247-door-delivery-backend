from __future__ import annotations

import time
from typing import Literal, Optional

from pydantic import BaseModel, Field


class FakeOnboardingPersonal(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    dob_day: Optional[int] = None
    dob_month: Optional[int] = None
    dob_year: Optional[int] = None


class FakeOnboardingAddress(BaseModel):
    line1: Optional[str] = None
    line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class FakeOnboardingBusinessProfile(BaseModel):
    business_type: Optional[str] = None
    product_description: Optional[str] = None
    website: Optional[str] = None


class FakeOnboardingBank(BaseModel):
    account_holder_name: Optional[str] = None
    account_number: Optional[str] = None
    sort_code: Optional[str] = None
    bank_name: Optional[str] = None


class FakeOnboardingAttestations(BaseModel):
    tos_accepted: Optional[bool] = None
    identity_confirmed: Optional[bool] = None
    information_accurate: Optional[bool] = None


class FakeOnboardingDraftIn(BaseModel):
    personal: Optional[FakeOnboardingPersonal] = None
    address: Optional[FakeOnboardingAddress] = None
    business_profile: Optional[FakeOnboardingBusinessProfile] = None
    bank: Optional[FakeOnboardingBank] = None
    attestations: Optional[FakeOnboardingAttestations] = None
    return_url: Optional[str] = None


class FakeOnboardingStatusOut(BaseModel):
    provider: Literal["fake"] = "fake"
    account_id: Optional[str] = None
    status: Literal["not_started", "in_progress", "completed"] = "not_started"
    draft: dict = Field(default_factory=dict)
    completion: Optional[dict] = None
    required_missing: list[str] = Field(default_factory=list)
    return_url: Optional[str] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
    completed_at: Optional[int] = None


class FakeOnboardingCompleteOut(BaseModel):
    provider: Literal["fake"] = "fake"
    account_id: str
    status: Literal["completed"] = "completed"
    redirect_url: Optional[str] = None
    completed_at: int = Field(default_factory=lambda: int(time.time()))
