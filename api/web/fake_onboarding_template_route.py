from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parents[2]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/web/payouts", tags=["Web Payouts"])


@router.get("/fake/onboarding", include_in_schema=False)
async def fake_driver_onboarding_page(
    request: Request,
    token: Optional[str] = Query(default=None, description="Driver bearer access token"),
    return_url: Optional[str] = Query(default=None, description="Frontend completion return URL"),
    account_id: Optional[str] = Query(default=None, description="Provider account identifier"),
):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing onboarding token in query parameters",
        )

    return templates.TemplateResponse(
        "fake_onboarding_template.html",
        {
            "request": request,
            "token": token,
            "account_id": account_id,
            "return_url": return_url,
            "request_id": getattr(request.state, "request_id", None),
            "load_url": "/api/v1/drivers/payout/onboarding/fake",
            "save_url": "/api/v1/drivers/payout/onboarding/fake",
            "complete_url": "/api/v1/drivers/payout/onboarding/fake/complete",
        },
    )
