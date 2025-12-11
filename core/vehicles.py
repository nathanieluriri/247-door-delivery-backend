
# ----------Vehicle subModel --------
from enum import Enum
from pydantic import BaseModel

from pydantic import BaseModel
from enum import Enum

class VehicleName(str, Enum):
    MOTOR_BIKE = "MOTOR_BIKE"
    CAR = "CAR"

class VehiclePricing(BaseModel):
    description: str
    seats: int
    use: str
    base_fare: float
    distance_rate: float   # rate per unit distance
    time_rate: float       # rate per unit time

class Vehicle(Enum):
    MOTOR_BIKE = VehiclePricing(
        description="Delivers small items",
        seats=0,
        use="Send small parcels",
        base_fare=2.0,
        distance_rate=1.0,
        time_rate=0.2
    )

    CAR = VehiclePricing(
        description="Cars from 2008 and above",
        seats=4,
        use="Transport people",
        base_fare=4.0,
        distance_rate=2.0,
        time_rate=0.4
    )



