import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from security import account_status_checks


def test_check_rider_rating_gate_blocks_when_pending(monkeypatch):
    async def _mock_pending(_user_id, _user_type):
        return {"rideId": "ride-77", "code": "RATING_REQUIRED_RIDER"}

    monkeypatch.setattr(
        account_status_checks, "find_pending_rating_for_user", _mock_pending
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            account_status_checks.check_rider_rating_gate(
                request=SimpleNamespace(),
                token=SimpleNamespace(userId="rider-1"),
            )
        )

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "RATING_REQUIRED_RIDER"


def test_check_driver_rating_gate_passes_without_pending(monkeypatch):
    async def _mock_pending(_user_id, _user_type):
        return None

    monkeypatch.setattr(
        account_status_checks, "find_pending_rating_for_user", _mock_pending
    )

    allowed = asyncio.run(
        account_status_checks.check_driver_rating_gate(
            request=SimpleNamespace(),
            token=SimpleNamespace(userId="driver-1"),
        )
    )
    assert allowed is True
