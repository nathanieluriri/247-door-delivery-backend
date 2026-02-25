import pytest
from fastapi import HTTPException

from core.payments.fake_provider import FakePaymentProvider
from core.payments.types import PaymentIntentRequest, PaymentStatus


class _InsertResult:
    def __init__(self, acknowledged: bool = True, inserted_id: str = "1"):
        self.acknowledged = acknowledged
        self.inserted_id = inserted_id


class _Collection:
    def __init__(self):
        self.items: dict[str, dict] = {}

    async def find_one(self, filter_dict: dict):
        reference = filter_dict.get("reference")
        if reference is None:
            return None
        payload = self.items.get(reference)
        return None if payload is None else dict(payload)

    async def insert_one(self, document: dict):
        self.items[document["reference"]] = dict(document)
        return _InsertResult()

    async def update_one(self, filter_dict: dict, update: dict):
        reference = filter_dict.get("reference")
        current = self.items.get(reference, {})
        current.update(update.get("$set", {}))
        self.items[reference] = current
        return None


class _FakeDB:
    def __init__(self):
        self.test_payment_intent = _Collection()


@pytest.mark.asyncio
async def test_fake_provider_create_fetch_refund_flow(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr("core.payments.fake_provider.db", fake_db)

    provider = FakePaymentProvider(base_url="http://localhost:8000")
    intent = await provider.create_intent(
        PaymentIntentRequest(
            reference="ride:123",
            amount_minor=1500,
            currency="gbp",
            customer_email="rider@example.com",
            metadata={"ride_id": "123"},
        )
    )

    assert intent.checkout_url.endswith("/api/v1/payments/fake/checkout/ride:123")
    assert intent.status == PaymentStatus.PENDING

    tx = await provider.fetch_transaction("ride:123")
    assert tx.status == PaymentStatus.PENDING

    refunded = await provider.refund("ride:123", amount_minor=500)
    assert refunded.status == PaymentStatus.REFUNDED


@pytest.mark.asyncio
async def test_fake_provider_rejects_invalid_webhook_payload(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr("core.payments.fake_provider.db", fake_db)

    provider = FakePaymentProvider(base_url="http://localhost:8000", webhook_secret_hash="secret")

    with pytest.raises(HTTPException) as bad_sig:
        await provider.verify_webhook(b"{}", {"verif-hash": "bad"})
    assert bad_sig.value.status_code == 401

    with pytest.raises(HTTPException) as bad_json:
        await provider.verify_webhook(b"invalid-json", {"verif-hash": "secret"})
    assert bad_json.value.status_code == 400
