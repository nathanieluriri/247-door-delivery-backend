from schemas.imports import ALLOWED_RIDE_STATUS_TRANSITIONS, RideStatus
from schemas.ride import NoDriverDecisionIn


def test_scheduled_transition_contract():
    assert RideStatus.scheduled in ALLOWED_RIDE_STATUS_TRANSITIONS
    assert RideStatus.matching in ALLOWED_RIDE_STATUS_TRANSITIONS[RideStatus.scheduled]
    assert RideStatus.awaitingPayment in ALLOWED_RIDE_STATUS_TRANSITIONS[RideStatus.drivingToDestination]
    assert RideStatus.completed in ALLOWED_RIDE_STATUS_TRANSITIONS[RideStatus.awaitingPayment]


def test_no_driver_decision_schema():
    keep = NoDriverDecisionIn(decision="keep_searching")
    cancel = NoDriverDecisionIn(decision="cancel_ride")
    assert keep.decision == "keep_searching"
    assert cancel.decision == "cancel_ride"
