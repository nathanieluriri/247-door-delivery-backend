from core.vehicles import Vehicle
from services.place_service import calculate_fare_using_vehicle_config_and_distance


def test_pricing_uses_server_side_values():
    # distance 10km, time 600s
    fare = calculate_fare_using_vehicle_config_and_distance(
        vehicle=Vehicle.CAR,
        distance=10_000,
        time=600,
    )
    # Base 4 + distance_rate*10000 + time_rate*600
    expected = Vehicle.CAR.value.base_fare + (Vehicle.CAR.value.distance_rate * 10_000) + (Vehicle.CAR.value.time_rate * 600)
    assert fare == expected
