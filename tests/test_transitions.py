import pytest

from schemas.imports import ALLOWED_RIDE_STATUS_TRANSITIONS, RideStatus


def test_allowed_transitions_forward_only():
    for state, allowed in ALLOWED_RIDE_STATUS_TRANSITIONS.items():
        # No state should allow transition to itself
        assert state not in allowed


@pytest.mark.parametrize(
    "current, target, valid",
    [
        (RideStatus.pendingPayment, RideStatus.findingDriver, True),
        (RideStatus.findingDriver, RideStatus.arrivingToPickup, True),
        (RideStatus.findingDriver, RideStatus.completed, False),
        (RideStatus.arrivingToPickup, RideStatus.pendingPayment, False),
        (RideStatus.drivingToDestination, RideStatus.completed, True),
    ],
)
def test_transition_matrix(current, target, valid):
    allowed = ALLOWED_RIDE_STATUS_TRANSITIONS[current]
    assert (target in allowed) is valid
