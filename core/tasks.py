from services.ride_service import remove_ride
ASYNC_TASK_REGISTRY = {
    "delete_ride": remove_ride,
 
}
