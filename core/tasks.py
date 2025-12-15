from services.driver_service import ban_drivers
from services.ride_service import remove_ride, update_ride_with_ride_id
from services.rider_service import ban_riders
from services.stripe_event_service import add_stripe_event


ASYNC_TASK_REGISTRY = {
    "ban_drivers":ban_drivers,
    "ban_riders":ban_riders,
    "delete_ride": remove_ride,
    "add_stripe_event":add_stripe_event,
    "update_ride_with_ride_id":update_ride_with_ride_id
}
