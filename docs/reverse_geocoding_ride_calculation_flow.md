# Reverse Geocoding + Ride Calculation Frontend Flow

## Goal
Define the exact frontend call sequence for:
- turning device coordinates into a valid `place_id` (reverse geocoding),
- calculating route distance/ETA/fare before checkout,
- creating the ride with the same place identifiers used for estimation.

Base API prefix: `/api/v1`

## Endpoints Used
1. `GET /riders/place/allowedCountries` (public)
2. `GET /riders/place/reverse-geocode` (public)
3. `GET /riders/place/autocomplete` (public)
4. `GET /riders/place/details` (public)
5. `POST /riders/place/calculate-fare` (public)
6. `POST /riders/ride/request` (rider auth required)
7. `GET /riders/ride/{rideId}` (rider auth required)

## Request/Response Envelope
Most endpoints return:

```json
{
  "status_code": 200,
  "data": {},
  "detail": "..."
}
```

## Recommended Frontend Sequence
### 1) Load allowed countries (app bootstrap)
Call:
- `GET /api/v1/riders/place/allowedCountries`

Use response `data` to constrain country selectors and autocomplete/reverse-geocode inputs.

### 2) Resolve current pickup from device GPS (reverse geocoding)
When rider taps "Use current location", call:
- `GET /api/v1/riders/place/reverse-geocode?lat=<LAT>&lng=<LNG>&country=<optional_country_code>`

Constraints:
- `lat` must be `-90..90`
- `lng` must be `-180..180`
- `country` should be one of allowed codes (for example `us`, `ng`, `ca`)

Typical response `data`:

```json
{
  "place_id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
  "description": "5th Ave, New York, NY, USA",
  "name": "5th Ave, New York, NY, USA",
  "address": "5th Ave, New York, NY, USA",
  "lat": 40.775594,
  "lng": -73.965455
}
```

If no match:
- `status_code=200`, `data=null`, `detail="No matching place found"`
- Frontend should show manual address search UI fallback.
- Reverse-geocode responses are cached for up to 14 days per rounded coordinate/country key.

### 3) Resolve destination (and optional stops)
For typed search:
- `GET /api/v1/riders/place/autocomplete?input=<TEXT>&country=<COUNTRY_CODE>`

Notes:
- `input` must be at least 2 characters.
- `country` is required for autocomplete.
- Autocomplete and place-details responses are cached for up to 14 days.

After selection, keep the selected `place_id`.

Optional precision step:
- `GET /api/v1/riders/place/details?place_id=<PLACE_ID>`

Use this when you need canonical `name/address/lat/lng` before rendering confirmation screens.

For stops:
- collect stop `place_id`s as `string[]`.

### 4) Calculate fare/ETA before ride request
Call:
- `POST /api/v1/riders/place/calculate-fare`

Body:

```json
{
  "pickup": "PICKUP_PLACE_ID",
  "destination": "DESTINATION_PLACE_ID",
  "stops": ["STOP_PLACE_ID_1", "STOP_PLACE_ID_2"]
}
```

Response includes:
- `data.map.totalDistanceMeters`
- `data.map.totalDurationSeconds`
- `data.map.encodedPolyline`
- `data.map.legs[]` (segment-level distance/time)
- `data.bike_fare`
- `data.car_fare`

Vehicle pricing decision on frontend:
- If rider selected `MOTOR_BIKE`, display `bike_fare`.
- If rider selected `CAR`, display `car_fare`.

Recalculate when any of these changes:
- pickup place,
- destination place,
- stops,
- vehicle type selection UI (fare display switches between returned bike/car values).

### 5) Create ride using same place identities
Call:
- `POST /api/v1/riders/ride/request`
- Requires `Authorization: Bearer <RIDER_ACCESS_TOKEN>`

Recommended request body:

```json
{
  "pickup": {
    "place_id": "PICKUP_PLACE_ID",
    "name": "Pickup Label",
    "formatted_address": "Pickup Address",
    "longitude": -73.965455,
    "latitude": 40.775594
  },
  "destination": {
    "place_id": "DESTINATION_PLACE_ID",
    "name": "Destination Label",
    "formatted_address": "Destination Address",
    "longitude": -73.98513,
    "latitude": 40.758896
  },
  "stops": ["STOP_PLACE_ID_1"],
  "vehicleType": "CAR",
  "pickupSchedule": 0
}
```

Important:
- `pickup`/`destination` may be sent as plain `place_id` strings, but sending full objects is recommended for richer ride payloads.
- `pickupSchedule=0` means immediate ride.
- Scheduled rides must use a future Unix epoch in milliseconds.

Backend behavior on request:
- Re-resolves place IDs,
- recalculates route and fare server-side,
- creates ride with authoritative `price` and `map`.

Do not trust cached UI fare as final billing value.

### 6) Read ride details after creation
Use returned ride ID from step 5, then call:
- `GET /api/v1/riders/ride/{rideId}`

Use response fields:
- `data.price` (authoritative fare used by backend),
- `data.map` (route snapshot),
- `data.rideStatus`,
- `data.pickup`, `data.destination`, `data.stops`.

## Error Handling Matrix
### Reverse geocode
- `400`: invalid coordinates
- `500`: Google Maps API key not configured
- `200 + data=null`: no match found

### Autocomplete/details
- `400`: invalid input (`input` too short or missing place_id)
- `200 + empty/null data`: no results
- `429/403/502`: upstream Google error mapping

### Fare calculation
- `400`: invalid pickup/destination or route generation failure

### Ride request
- `401/403`: missing or invalid rider token
- `403`: rating gate (`detail.code = "RATING_REQUIRED_RIDER"`)
- `404`: no compatible drivers within 5km for immediate rides
- `400`: invalid places, invalid schedule, or route generation failure

## Frontend State Guidance
1. Keep `pickupPlaceId`, `destinationPlaceId`, and `stopPlaceIds[]` as the canonical state for all ride-estimation calls.
2. Re-run `calculate-fare` when place IDs change.
3. On submit, send the same place IDs to `/ride/request`.
4. After submit success, replace estimate UI values with values from created ride payload (`price` and `map`).
5. If reverse-geocode returns null, force manual place search before allowing estimate/submit.
