from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.templating import Jinja2Templates

from core.database import db


class PaymentPreview(TypedDict):
    title: str
    description: str
    reference: str
    provider: str
    currency: str
    amount_minor: int
    formatted_amount: str
    billing_period: str
    service_date: str


BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web/payments", tags=["Web Payments"])


def _format_minor_amount(amount_minor: int) -> str:
    return f"{amount_minor / 100:,.2f}"


def build_test_payment_preview() -> PaymentPreview:
    amount_minor = 129_900
    return {
        "title": "Marcus Cleaning Premium Deep Clean",
        "description": "One-time full apartment deep clean with eco-safe supplies and checklist report.",
        "reference": "MRC-TEMPLATE-2026-00231",
        "provider": "STRIPE",
        "currency": "USD",
        "amount_minor": amount_minor,
        "formatted_amount": _format_minor_amount(amount_minor),
        "billing_period": "One-time payment",
        "service_date": "Flexible scheduling within 7 days",
    }


def _build_payment_preview_from_row(row: dict[str, Any]) -> PaymentPreview:
    amount_minor = int(row.get("amount_minor", 0) or 0)
    metadata = row.get("metadata") or {}

    return {
        "title": str(metadata.get("title") or "Door Delivery Payment"),
        "description": str(
            metadata.get("description")
            or "Complete your payment to confirm your booking."
        ),
        "reference": str(row.get("reference") or ""),
        "provider": str(row.get("provider") or "FAKE").upper(),
        "currency": str(row.get("currency") or "GBP").upper(),
        "amount_minor": amount_minor,
        "formatted_amount": _format_minor_amount(amount_minor),
        "billing_period": str(metadata.get("billing_period") or "One-time payment"),
        "service_date": str(metadata.get("service_date") or "Service date to be confirmed"),
    }


async def _get_test_payment_intent(reference: str) -> dict[str, Any] | None:
    return await db.test_payment_intent.find_one({"reference": reference})


@router.get("/template", include_in_schema=False)
async def payment_template_page(request: Request):
    payment = build_test_payment_preview()
    return templates.TemplateResponse(
        "payment_template.html",
        {
            "request": request,
            "payment": payment,
            "request_id": getattr(request.state, "request_id", None),
            "complete_url_success": f"/api/v1/payments/fake/checkout/{payment['reference']}/complete?status=succeeded",
            "complete_url_failed": f"/api/v1/payments/fake/checkout/{payment['reference']}/complete?status=failed",
        },
    )


@router.get("/link/{reference}", include_in_schema=False)
async def payment_page(reference: str, request: Request):
    row = await _get_test_payment_intent(reference)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Test payment intent '{reference}' was not found",
        )

    payment = _build_payment_preview_from_row(row)
    return templates.TemplateResponse(
        "payment_template.html",
        {
            "request": request,
            "payment": payment,
            "request_id": getattr(request.state, "request_id", None),
            "complete_url_success": f"/api/v1/payments/fake/checkout/{reference}/complete?status=succeeded",
            "complete_url_failed": f"/api/v1/payments/fake/checkout/{reference}/complete?status=failed",
        },
    )
