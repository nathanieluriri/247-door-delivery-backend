Draft plan AI (todo list):
- Inspect existing ride schemas/services for share/link fields and any link-generation helpers or config values.
- Decide the share-link format (e.g., signed token or public ID) and update schema/model/repo as needed to store or compute it.
- Implement `generate_public_ride_sharing_link` in `api/v1/rider_route.py` plus any supporting service/repo changes.
- Add or update tests to cover authorized access and link generation behavior.



Draft plan User (todo list):
- The share link should be public and it should allow anyone receive updates on a ride whether a ride has been paid what status it is in and all that it should work in an interesting way 1.) generating link creates something in cache like userId of who created the share link , role whether its driver or rider or admin and then the id to the ride being shared then the share link takes the fronend_share_ride_url as a parameter then adds the id gotten from redis as a query parameter and returns it to the user and if a link is tried to be shared again first check redis for the ride id if it is in redis then send the details again don't create a new one over again
