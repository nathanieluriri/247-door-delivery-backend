# Accepting Ride Requests (Driver)

When a driver receives a `ride_request` event, they accept it by responding through the driver app/API with an **accept ride** action that references the request ID. 

The backend then marks the request as accepted, locks it to that driver, and sends a confirmation/update event back to both rider and driver so the ride can move to the next status.