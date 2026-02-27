import asyncio
from types import SimpleNamespace

from core.vehicles_config import VehicleType
from schemas.imports import RideStatus
from schemas.ride import RideOut
from services import ride_rating_service


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def __aiter__(self):
        async def _iter():
            for item in self._docs:
                yield item

        return _iter()


class _FakeRidesCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, *_args, **_kwargs):
        return _FakeCursor(self._docs)


class _FakeDb:
    def __init__(self, docs):
        self.rides = _FakeRidesCollection(docs)


def _sample_ride() -> RideOut:
    return RideOut(
        id="ride-1",
        pickup="pickup",
        destination="destination",
        vehicleType=VehicleType.CAR,
        userId="rider-1",
        driverId="driver-1",
        rideStatus=RideStatus.completed,
    )


def test_build_ride_rating_status_marks_pending(monkeypatch):
    async def _mock_get_rating(_filter):
        return None

    monkeypatch.setattr(ride_rating_service, "get_rating", _mock_get_rating)
    status = asyncio.run(ride_rating_service.build_ride_rating_status(_sample_ride()))

    assert status.riderMustRate is True
    assert status.driverMustRate is True
    assert status.riderRated is False
    assert status.driverRated is False


def test_build_ride_rating_status_marks_rated(monkeypatch):
    async def _mock_get_rating(filter_dict):
        if filter_dict["raterId"] == "rider-1":
            return SimpleNamespace(date_created=1111)
        if filter_dict["raterId"] == "driver-1":
            return SimpleNamespace(date_created=2222)
        return None

    monkeypatch.setattr(ride_rating_service, "get_rating", _mock_get_rating)
    status = asyncio.run(ride_rating_service.build_ride_rating_status(_sample_ride()))

    assert status.riderRated is True
    assert status.riderRatedAt == 1111
    assert status.driverRated is True
    assert status.driverRatedAt == 2222


def test_find_pending_rating_for_rider(monkeypatch):
    fake_db = _FakeDb(
        [
            {
                "_id": "ride-10",
                "userId": "rider-1",
                "driverId": "driver-9",
                "rideStatus": RideStatus.completed.value,
            }
        ]
    )

    async def _mock_get_rating(_filter):
        return None

    monkeypatch.setattr(ride_rating_service, "db", fake_db)
    monkeypatch.setattr(ride_rating_service, "get_rating", _mock_get_rating)

    pending = asyncio.run(
        ride_rating_service.find_pending_rating_for_user("rider-1", "rider")
    )
    assert pending == {"rideId": "ride-10", "code": "RATING_REQUIRED_RIDER"}
