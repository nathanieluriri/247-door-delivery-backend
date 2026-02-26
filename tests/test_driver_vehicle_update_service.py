from types import SimpleNamespace

import pytest

from core.vehicles_config import VehicleType
from schemas.driver import DriverVehicleUpdate
from services import driver_service


@pytest.mark.asyncio
async def test_update_driver_vehicle_persists_vehicle_fields(monkeypatch):
    captured: dict = {}

    async def fake_update_driver(filter_dict: dict, driver_data):
        captured["filter_dict"] = filter_dict
        captured["payload"] = driver_data.model_dump(exclude_none=True)
        return SimpleNamespace(id="69a02b3e5b7284be8bd80afa")

    monkeypatch.setattr(driver_service, "update_driver", fake_update_driver)

    payload = DriverVehicleUpdate(
        vehicleType=VehicleType.MOTOR_BIKE,
        vehicleMake="Yamaha",
        vehicleModel="FZ",
        vehicleColor="Red",
        vehiclePlateNumber="AB12-CDE",
        vehicleYear=2008,
    )

    result = await driver_service.update_driver_vehicle(
        driver_id="69a02b3e5b7284be8bd80afa",
        vehicle_details=payload,
    )

    assert result.id == "69a02b3e5b7284be8bd80afa"
    assert "filter_dict" in captured
    persisted = captured["payload"]
    assert persisted["vehicleType"] == VehicleType.MOTOR_BIKE
    assert persisted["vehicleMake"] == "Yamaha"
    assert persisted["vehicleModel"] == "FZ"
    assert persisted["vehicleColor"] == "Red"
    assert persisted["vehiclePlateNumber"] == "AB12-CDE"
    assert persisted["vehicleYear"] == 2008
    assert persisted["vehicleVerified"] is False
    assert persisted["vehicleVerifiedAt"] is None
    assert persisted["vehicleVerificationNotes"] is None
