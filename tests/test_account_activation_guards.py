import pytest
from pydantic import ValidationError

from core.staff_payment import _status_after_onboarding
from schemas.driver import DriverCreate, DriverSignup
from schemas.imports import AccountStatus


def test_onboarding_activates_only_drivers_waiting_for_verification():
    assert _status_after_onboarding(AccountStatus.PENDING_VERIFICATION, True) == AccountStatus.ACTIVE
    assert _status_after_onboarding(AccountStatus.PENDING_VERIFICATION, False) is None
    for sanctioned in (AccountStatus.SUSPENDED, AccountStatus.BANNED, AccountStatus.DEACTIVATED):
        assert _status_after_onboarding(sanctioned, True) is None
    assert _status_after_onboarding(None, True) is None


def test_driver_signup_rejects_short_passwords_before_hashing():
    with pytest.raises(ValidationError):
        DriverSignup(email="new.driver@example.com", password="short")
    assert DriverSignup(email="new.driver@example.com", password="long-enough-1").password != "long-enough-1"


def test_oauth_created_drivers_may_have_no_password():
    assert DriverCreate(email="oauth.driver@example.com", password="").email == "oauth.driver@example.com"
