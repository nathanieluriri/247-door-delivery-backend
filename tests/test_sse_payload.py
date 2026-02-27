from schemas.imports import RideStatus
from schemas.ride import RideRatingStatus
from schemas.sse import RideStatusUpdate


def test_ride_status_update_action_fields_serialize_with_aliases():
    payload = RideStatusUpdate(
        rideId="ride-123",
        status=RideStatus.matching,
        message="No driver available at pickup time",
        actionRequired=True,
        actionType="no_driver_decision",
        decisionOptions=["keep_searching", "cancel_ride"],
        actionDeadlineMs=1735689600000,
        reasonCode="no_driver_at_pickup",
        ratingStatus=RideRatingStatus(
            riderMustRate=True,
            driverMustRate=True,
            riderRated=False,
            driverRated=False,
        ),
    )

    data = payload.model_dump(by_alias=True, mode="json", exclude_none=True)

    assert data["rideId"] == "ride-123"
    assert data["status"] == RideStatus.matching.value
    assert data["actionRequired"] is True
    assert data["actionType"] == "no_driver_decision"
    assert data["decisionOptions"] == ["keep_searching", "cancel_ride"]
    assert data["actionDeadlineMs"] == 1735689600000
    assert data["reasonCode"] == "no_driver_at_pickup"
    assert data["ratingStatus"]["riderMustRate"] is True
    assert data["ratingStatus"]["driverMustRate"] is True
