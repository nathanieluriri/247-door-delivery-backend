from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PaymentProviderName(str, Enum):
    STRIPE = "stripe"
    FAKE = "fake"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


@dataclass(frozen=True, slots=True)
class PaymentIntentRequest:
    reference: str
    amount_minor: int
    currency: str
    customer_email: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentIntentResponse:
    provider: PaymentProviderName
    reference: str
    status: PaymentStatus
    checkout_url: str
    provider_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    provider: PaymentProviderName
    event_id: str
    event_type: str
    payload: dict[str, Any]
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentTransaction:
    provider: PaymentProviderName
    reference: str
    status: PaymentStatus
    raw: dict[str, Any] = field(default_factory=dict)
