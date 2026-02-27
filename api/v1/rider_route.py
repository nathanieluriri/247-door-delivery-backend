import os
import time
from fastapi import APIRouter, HTTPException, Query, Request, status, Path,Depends
from typing import List, Literal, Union, get_args
from fastapi.responses import RedirectResponse
from core.countries import ALLOWED_COUNTRIES
from core.payments import PaymentService, get_payment_service
from core.vehicles import Vehicle
from core.vehicles_config import VehicleType
from schemas.address import AddressBase, AddressCreate, AddressOut, AddressUpdate
from schemas.imports import ResetPasswordConclusion, ResetPasswordInitiation, ResetPasswordInitiationResponse, RideStatus
from schemas.place import FareBetweenPlacesCalculationRequest, FareBetweenPlacesCalculationResponse, Location, PlaceBase
from schemas.rating import RatingBase, RatingCreate
from schemas.response_schema import APIResponse
from schemas.ride import NoDriverDecisionIn, RideBase, RideCreate, RideOut, RideShareLinkOut, RideUpdate
from schemas.tokens_schema import accessTokenOut
from core.routing_config import maps
from schemas.rider_schema import (
    RiderCreate,
    RiderOut,
    RiderBase,
    RiderUpdate,
    RiderPhoneUpdate,
    RiderRefresh,
    LoginType,
    RiderUpdatePassword,
)
from repositories.tokens_repo import delete_access_token, delete_refresh_tokens_by_previous_access_token
from security.account_status_checks import check_rider_account_status, check_rider_rating_gate
from services.address_service import add_address, remove_address, retrieve_address_by_user_id, update_address_by_id
from services.place_service import (
    calculate_fare_using_vehicle_config_and_distance,
    get_autocomplete,
    get_place_details,
    get_reverse_geocode,
)
from services.rating_service import add_rating, retrieve_rating_by_user_id
from services.ride_service import add_ride, decide_no_driver_for_ride, generate_public_ride_sharing_link_for_rider, retrieve_rides_by_user_id, retrieve_rides_by_user_id_and_ride_id, retrieve_shared_ride_by_share_id, update_ride_by_id
from services.sse_service import list_eligible_driver_ids_for_request
from services.rider_service import (
    add_rider,
    remove_rider,
    retrieve_riders,
    authenticate_rider,
    retrieve_rider_by_rider_id,
    rider_reset_password_conclusion,
    rider_reset_password_initiation,
    update_rider_by_id,
    refresh_rider_tokens_reduce_number_of_logins,
    oauth
)
from security.auth import verify_token,verify_token_to_refresh, verify_token_rider_role
from security.oauth_return import (
    append_query_params,
    build_oauth_state,
    parse_oauth_state_or_raise,
    resolve_default_frontend_base,
    resolve_return_url_or_raise,
)
from services.notification_targets import register_push_token, has_push_tokens
from schemas.notification import PushTokenRegister
from dotenv import load_dotenv 
load_dotenv()

router = APIRouter(prefix="/riders", tags=["Riders"])

ERROR_PAGE_URL = os.getenv("RIDER_ERROR_PAGE_URL") or os.getenv("ERROR_PAGE_URL")


def _extract_place_id(place: object, field_name: str) -> str:
    if isinstance(place, str):
        place_id = place.strip()
    elif isinstance(place, dict):
        place_id = str(place.get("place_id") or "").strip()
    else:
        place_id = str(getattr(place, "place_id", "") or "").strip()

    if not place_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must include a valid place_id",
        )
    return place_id

# --- Step 1: Redirect user to Google login ---
@router.get(
    "/google/auth",
    summary="Start rider Google OAuth",
    description="Redirects the rider to Google OAuth to begin authentication.",
)
async def login_with_google_account(
    request: Request,
    next: str | None = Query(
        default=None,
        description="Optional frontend URL/path to return to after OAuth callback.",
    ),
):
    """
    Begin Google OAuth login for riders and redirect to the provider.

    Access: Public (no auth).
    """
    if not oauth or not oauth.google:
        raise HTTPException(status_code=500, detail="OAuth configuration not initialized")
    backend_host = request.url.hostname or ""
    requested_next = next or request.headers.get("referer")
    try:
        return_url = resolve_return_url_or_raise(
            role="rider",
            backend_host=backend_host,
            next_url=requested_next,
        )
    except HTTPException:
        if next is not None:
            raise
        return_url = resolve_default_frontend_base("rider", backend_host=backend_host)
    state = build_oauth_state(role="rider", return_url=return_url)
    request.session["oauth_state_rider"] = state
    request.session["oauth_return_url_rider"] = return_url
    redirect_uri = str(request.url_for("auth_callback_rider"))
    return await oauth.google.authorize_redirect(
        request=request,
        redirect_uri=redirect_uri,
        state=state,
    )


# --- Step 2: Handle callback from Google ---
@router.get(
    "/auth/callback",
    summary="Rider Google OAuth callback",
    description="Handles Google OAuth callback, creates or authenticates the rider, and returns tokens.",
)
async def auth_callback_rider(request: Request):
    """
    Handle Google OAuth callback for riders and issue tokens.

    Access: Public (no auth).
    """
    if not oauth or not oauth.google:
        raise HTTPException(status_code=500, detail="OAuth configuration not initialized")
    backend_host = request.url.hostname or ""
    default_error_url = append_query_params(
        ERROR_PAGE_URL or resolve_default_frontend_base("rider", backend_host=backend_host),
        {"status": "failed", "reason": "oauth_callback_failed"},
    )
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(url=default_error_url, status_code=status.HTTP_302_FOUND)

    incoming_state = request.query_params.get("state")
    try:
        state_return_url = parse_oauth_state_or_raise(
            role="rider",
            state=incoming_state,
            backend_host=backend_host,
        )
    except HTTPException:
        return RedirectResponse(url=default_error_url, status_code=status.HTTP_302_FOUND)
    session_state = request.session.pop("oauth_state_rider", None)
    session_return_url = request.session.pop("oauth_return_url_rider", None)
    if session_state and incoming_state != session_state:
        mismatch_url = append_query_params(
            ERROR_PAGE_URL or resolve_default_frontend_base("rider", backend_host=backend_host),
            {"status": "failed", "reason": "oauth_state_mismatch"},
        )
        return RedirectResponse(url=mismatch_url, status_code=status.HTTP_302_FOUND)
    if session_return_url:
        try:
            validated_session_return = resolve_return_url_or_raise(
                role="rider",
                backend_host=backend_host,
                next_url=session_return_url,
            )
        except HTTPException:
            return RedirectResponse(url=default_error_url, status_code=status.HTTP_302_FOUND)
        if validated_session_return != state_return_url:
            mismatch_url = append_query_params(
                ERROR_PAGE_URL
                or resolve_default_frontend_base("rider", backend_host=backend_host),
                {"status": "failed", "reason": "oauth_return_url_mismatch"},
            )
            return RedirectResponse(url=mismatch_url, status_code=status.HTTP_302_FOUND)
    final_return_url = session_return_url or state_return_url

    user_info = token.get('userinfo')

    # Just print or return user info for now
    if user_info:
        print("✅ Google user info:", user_info)
        rider = RiderBase(
            firstName=user_info['name'],
            password='',
            lastName=user_info['given_name'],
            email=user_info['email'],
            loginType=LoginType.google,
        )
        data = await authenticate_rider(user_data=rider)
        if data == None:
            new_rider = RiderCreate(**rider.model_dump())
            items = await add_rider(user_data=new_rider)

            access_token = items.access_token
            refresh_token = items.refresh_token
        else:
            access_token = data.access_token
            refresh_token = data.refresh_token

        success_url = append_query_params(
            final_return_url,
            {
                "status": "success",
                "access_token": access_token,
                "refresh_token": refresh_token,
            }, # type: ignore
        )
        response = RedirectResponse(
            url=success_url,
            status_code=status.HTTP_302_FOUND
        )
        return response

    error_url = append_query_params(
        ERROR_PAGE_URL or resolve_default_frontend_base("rider", backend_host=backend_host),
        {"status": "failed", "reason": "oauth_user_info_missing"},
    )
    return RedirectResponse(url=error_url, status_code=status.HTTP_302_FOUND)


@router.post(
    "/push/register",
    response_model=APIResponse[list[str]],
    dependencies=[Depends(verify_token_rider_role), Depends(check_rider_account_status)],
    summary="Register rider push token",
    description="Registers a OneSignal player ID for push notifications.",
)
async def register_rider_push_token(
    payload: PushTokenRegister,
    token: accessTokenOut = Depends(verify_token_rider_role),
):
    tokens = await register_push_token(
        user_type="rider",
        user_id=token.userId,
        player_id=payload.player_id,
    )
    return APIResponse(status_code=200, data=tokens, detail="Push token registered")


@router.get(
    "/push/status",
    response_model=APIResponse[dict],
    dependencies=[Depends(verify_token_rider_role), Depends(check_rider_account_status)],
    summary="Rider push status",
    description="Returns whether the rider has any push tokens registered.",
)
async def get_rider_push_status(
    token: accessTokenOut = Depends(verify_token_rider_role),
):
    enabled = await has_push_tokens("rider", token.userId)
    return APIResponse(
        status_code=200,
        data={"enabled": enabled},
        detail="Push status retrieved",
    )

@router.get(
    "/",
    response_model_exclude={"data": {"__all__": {"password"}}},
    response_model=APIResponse[List[RiderOut]],
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token)],
    summary="List riders",
    description="Returns a paginated list of riders.",
)
async def list_riders(start:int= 0, stop:int=100):
    """
    List riders (admin/system usage).

    Access: Any authenticated user (valid access token required).
    """
    items = await retrieve_riders(start=start,stop=stop)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")

@router.get(
    "/profile",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[RiderOut],
    dependencies=[Depends(verify_token_rider_role)],
    response_model_exclude_none=True,
    summary="Get my rider profile",
    description="Returns the authenticated rider's profile details.",
)
async def get_my_rider_details(token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Fetch the authenticated rider's profile.

    Access: Rider only (valid rider access token required).
    """
    items = await retrieve_rider_by_rider_id(id=token.userId)
    return APIResponse(status_code=200, data=items, detail="users items fetched")

 


@router.post(
    "/signup",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[RiderOut],
    summary="Register rider",
    description="Creates a new rider account using email and password.",
)
async def signup_new_rider(user_data:RiderBase):
    """
    Register a new rider account.

    Access: Public (no auth).
    """
    new_rider = RiderCreate(**user_data.model_dump())
    items = await add_rider(user_data=new_rider)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.post(
    "/login",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[RiderOut],
    summary="Rider login",
    description="Authenticates a rider and returns access and refresh tokens.",
)
async def login_rider(user_data:RiderBase):
    """
    Authenticate a rider and return access/refresh tokens.

    Access: Public (no auth).
    """
    items = await authenticate_rider(user_data=user_data)
   
     
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.post(
    "/refresh",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[RiderOut],
    dependencies=[Depends(verify_token_to_refresh)],
    summary="Refresh rider tokens",
    description="Refreshes an expired access token using a valid refresh token.",
)
async def refresh_rider_tokens(user_data:RiderRefresh,token:accessTokenOut = Depends(verify_token_to_refresh)):
    """
    Refresh an expired rider access token using a refresh token.

    Access: Rider only (expired access token in header + refresh token in body).
    """
    
    items= await refresh_rider_tokens_reduce_number_of_logins(user_refresh_data=user_data,expired_access_token=token.accesstoken)

    return APIResponse(status_code=200, data=items, detail="users items fetched")


@router.delete(
    "/account",
    dependencies=[Depends(verify_token_rider_role)],
    summary="Delete rider account",
    description="Deletes the authenticated rider account.",
)
async def delete_rider_account(token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Delete the authenticated rider account.

    Access: Rider only (valid rider access token required).
    """
    result = await remove_rider(user_id=token.userId)
    return result

@router.post(
    "/logout",
    dependencies=[Depends(verify_token_rider_role)],
    summary="Logout rider",
    description="Invalidates the rider's access and refresh tokens.",
)
async def logout_rider(token: accessTokenOut = Depends(verify_token_rider_role)):
    """
    Invalidate access and refresh tokens for the rider.

    Access: Rider only (valid rider access token required).
    """
    if not token.accesstoken:
        raise HTTPException(status_code=400, detail="Invalid access token")
    await delete_refresh_tokens_by_previous_access_token(accessToken=token.accesstoken)
    deleted = await delete_access_token(accessToken=token.accesstoken)
    if not deleted:
        raise HTTPException(status_code=400, detail="Access token already invalidated")
    return APIResponse(status_code=200, data=True, detail="Logged out successfully")

@router.patch(
    "/profile",
    summary="Update rider profile",
    description="Updates the authenticated rider profile fields.",
)
async def update_rider_profile(rider_details:RiderUpdate,token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Update the authenticated rider profile.

    Access: Rider only (valid rider access token required).
    """
    rider = await update_rider_by_id(user_id=token.userId,user_data=rider_details)
    return APIResponse(data=rider,detail="Rider Profile updated successfully", status_code=200)


@router.patch(
    "/profile/phone",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[RiderOut],
    dependencies=[Depends(verify_token_rider_role)],
    summary="Update rider phone number",
    description="Updates only the authenticated rider's phone number.",
)
async def update_rider_phone_number(
    payload: RiderPhoneUpdate,
    token: accessTokenOut = Depends(verify_token_rider_role),
):
    """
    Update the authenticated rider's phone number.

    Access: Rider only (valid rider access token required).
    """
    rider = await update_rider_by_id(
        user_id=token.userId,
        user_data=RiderUpdate(phoneNumber=payload.phoneNumber),
    )
    return APIResponse(data=rider, detail="Rider phone number updated successfully", status_code=200)

# -------------------------------
# -------RATING MANAGEMENT------- 
# -------------------------------


@router.get(
    "/rating",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    summary="Get rider rating",
    description="Returns rating summary for the authenticated rider.",
)
async def view_rating(token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Retrieve the authenticated rider's rating summary.

    Access: Rider only (valid rider access token required).
    """
    rating = await retrieve_rating_by_user_id(user_id=token.userId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.get(
    "/driver/{driverId}/rating",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    summary="Get driver rating",
    description="Returns rating summary for a driver by ID.",
)
async def view_driver_rating(driverId:str):
    """
    Retrieve a driver's rating by driver ID.

    Access: Rider only (valid rider access token required).
    """
    rating = await retrieve_rating_by_user_id(user_id=driverId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.post(
    "/rate/driver",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    summary="Rate a driver",
    description="Submits a rating for a driver after a completed ride.",
)
async def rate_driver_after_ride(rating_data:RatingBase,token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Submit a rating for a driver after a completed ride.

    Access: Rider only (valid rider access token required).
    """
    
    rider_rating = RatingCreate(**rating_data.model_dump(),raterId=token.userId)
    rating = await add_rating(rating_data=rider_rating, riderId=token.userId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Rated Driver")




# --------------------------------
# -------ADDRESS MANAGEMENT------- 
# --------------------------------

@router.get(
    "/addresses",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    response_model=APIResponse[List[AddressOut]],
    summary="List saved addresses",
    description="Returns saved addresses for the authenticated rider.",
)
async def view_all_previous_addresses_created_by_user(token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    List saved addresses for the authenticated rider.

    Access: Rider only (valid rider access token required).
    """
    
    address = await retrieve_address_by_user_id(userId=token.userId)
    return APIResponse(data=address,status_code=200,detail="Successfully retrieved Addresses")

@router.post(
    "/address",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    response_model=APIResponse[AddressOut],
    summary="Create saved address",
    description="Creates a new saved address for the authenticated rider.",
)
async def create_new_address_for_a_user(address_data:AddressBase,token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Create a new saved address for the authenticated rider.

    Access: Rider only (valid rider access token required).
    """
 
    new_address_data = AddressCreate(**address_data.model_dump(),userId=token.userId)
    address = await add_address(address_data=new_address_data)
    return APIResponse(data = address,status_code=200,detail="Successfully created new Address")


@router.delete(
    "/address/{addressId}",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    response_model=APIResponse[Literal[True]],
    summary="Delete saved address",
    description="Deletes a saved address by its identifier.",
)
async def delete_address_detials_using_address_id(addressId:str,token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Delete a saved address by its ID.

    Access: Rider only (valid rider access token required).
    """
    
    removed_address = await remove_address(address_id=addressId,user_id=token.userId)
    return APIResponse(data=removed_address,detail="Successfully deleted Address",status_code= 200)



@router.patch(
    "/address/{addressId}",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    response_model=APIResponse[AddressOut],
    summary="Update saved address",
    description="Updates the label or place ID for a saved address.",
)
async def update_address_label(addressId:str,address_data:AddressUpdate,token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Update a saved address label or details.

    Access: Rider only (valid rider access token required).
    """
     
    address = await update_address_by_id(address_id=addressId,address_data=address_data,user_id=token.userId)
    return APIResponse(data=address,status_code=200,detail = "Successfully updated addres")


# -------------------------------
# ------- PLACES MANAGEMENT ------- 
# -------------------------------
@router.get(
    "/place/allowedCountries",
    response_model=APIResponse[List[str]],
    summary="Get allowed countries for place lookup",
    description="Lists allowed countries used for place lookups.",
)
async def allowed_countries():
    """
    List allowed countries for place lookups.

    Access: Public (no auth).
    """
    return APIResponse(
        data=list(get_args(ALLOWED_COUNTRIES)),
        detail="Allowed countries retrieved",
        status_code=200,
    )


@router.get(
    "/place/autocomplete",
    response_model=APIResponse[Union[List[PlaceBase],None]],
    summary="Get location suggestions (cached for 14 days)",
    description="Returns autocomplete suggestions for a partial place query.",
)
async def autocomplete(
    input: str = Query(..., description="User input text for autocomplete"),
    country: ALLOWED_COUNTRIES = Query(..., description="Choose one of them ")
):
    """
    Return location autocomplete suggestions.

    Access: Public (no auth).
    """
    return await get_autocomplete(input, country)



@router.get(
    "/place/details",
     
    summary="Get place details (cached for 14 days)",
    description="Returns detailed information for a Google Place ID.",
)
async def place_details(
    place_id: str = Query(..., description="Google Place ID")
):
    """
    Return full details for a given place.

    Access: Public (no auth).
    """
    return await get_place_details(place_id)

@router.get(
    "/place/reverse-geocode",
    response_model=APIResponse[Union[PlaceBase, None]],
    summary="Resolve current coordinates to place_id",
    description="Returns a place payload for supplied coordinates, including place_id.",
)
async def reverse_geocode(
    lat: float = Query(..., ge=-90, le=90, description="Latitude in decimal degrees"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude in decimal degrees"),
    country: ALLOWED_COUNTRIES | None = Query(None, description="Optional country filter"),
):
    """
    Resolve latitude and longitude to a place structure that includes place_id.

    Access: Public (no auth).
    """
    return await get_reverse_geocode(latitude=lat, longitude=lng, country=country)




@router.post(
    "/place/calculate-fare",
    summary="Use place id for pickup, destination & stops to calculate fair price return distance, eta and fare price ",
    description="Calculates fare, route distance, and ETA based on place IDs and vehicle type.",
    response_model=APIResponse[FareBetweenPlacesCalculationResponse]
)
async def calculate_fare_price(data:FareBetweenPlacesCalculationRequest):
    """
    Calculate fare and route details for the supplied place IDs.

    Access: Public (no auth).
    """
    pick_up = await get_place_details(place_id=data.pickup)
    drop_off = await get_place_details(place_id=data.destination)
   
    if not pick_up or not pick_up.data:
        raise HTTPException(status_code=400, detail="Invalid pickup location")
    if not drop_off or not drop_off.data:
        raise HTTPException(status_code=400, detail="Invalid destination location")
    
    origin = (pick_up.data.get("lat"),pick_up.data.get("lng"))
    destination = (drop_off.data.get("lat"),drop_off.data.get("lng"))
    stops: list = []
    if data.stops:
        for stop in data.stops:
            _place_details =await get_place_details(place_id=stop)
            if _place_details.data is not None:
                stops.append((_place_details.data['lat'],_place_details.data['lng']))
    
    map = maps.get_delivery_route(origin=origin,destination=destination,stops=stops or [])
    
    if not map:
        raise HTTPException(status_code=400, detail="Unable to calculate route")
    
    bike_calculation = calculate_fare_using_vehicle_config_and_distance(distance=map.totalDistanceMeters,time=map.totalDurationSeconds,vehicle=Vehicle.MOTOR_BIKE,)
    car_calculation = calculate_fare_using_vehicle_config_and_distance(distance=map.totalDistanceMeters,time=map.totalDurationSeconds,vehicle=Vehicle.CAR,)
    fare = FareBetweenPlacesCalculationResponse(origin=Location(latitude=pick_up.data["lat"],longitude=pick_up.data["lng"]),bike_fare=bike_calculation,car_fare=car_calculation,map=map)
    
    return APIResponse(status_code=200,detail="Successfully calculated far",data= fare)

# -------------------------------
# ------- RIDE MANAGEMENT ------- 
# -------------------------------

@router.get(
    "/ride/history",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    response_model=APIResponse[List[RideOut]],
    summary="Get rider ride history",
    description="Returns past rides for the authenticated rider.",
)
async def ride_history(token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    List ride history for the authenticated rider.

    Access: Rider only (valid rider access token required).
    """
    rides = await retrieve_rides_by_user_id(user_id=token.userId)
    return APIResponse(data = rides, status_code=200, detail = "Successfully retrieved Ride history")

 
@router.post(
    "/ride/request",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role), Depends(check_rider_rating_gate)],
    response_model=APIResponse[RideOut],
    summary="Request a ride",
    description="Creates a new ride request after calculating fare and route details.",
)
async def requesting_a_new_ride_or_delivery_request(data:RideBase,token:accessTokenOut = Depends(verify_token_rider_role),payment_service: PaymentService = Depends(get_payment_service)):
    """
    Request a new ride, calculate fare, and dispatch to nearby drivers.

    Access: Rider only (valid rider access token required).
    """
    pickup_place_id = _extract_place_id(data.pickup, "pickup")
    destination_place_id = _extract_place_id(data.destination, "destination")
    pick_up = await get_place_details(place_id=pickup_place_id)
    drop_off = await get_place_details(place_id=destination_place_id)
   
    if not pick_up or not pick_up.data:
        raise HTTPException(status_code=400, detail="Invalid pickup location")
    if not drop_off or not drop_off.data:
        raise HTTPException(status_code=400, detail="Invalid destination location")
    
    origin = (pick_up.data["lat"],pick_up.data["lng"])
    now_ms = int(time.time() * 1000)
    pickup_schedule_ms = int(data.pickupSchedule or 0)
    if pickup_schedule_ms < 0:
        raise HTTPException(status_code=400, detail="pickupSchedule must be 0 or a future Unix epoch in milliseconds")

    is_scheduled = pickup_schedule_ms > 0
    if is_scheduled and pickup_schedule_ms <= now_ms:
        raise HTTPException(status_code=400, detail="pickupSchedule must be a future Unix epoch in milliseconds")

    if not is_scheduled:
        eligible_driver_ids = await list_eligible_driver_ids_for_request(
            pickup_location=(pick_up.data["lat"], pick_up.data["lng"]),
            vehicle_type=data.vehicleType.value,
        )
        if not eligible_driver_ids:
            raise HTTPException(
                status_code=404,
                detail="No compatible drivers available for requested vehicle type within 5km.",
            )

    destination = (drop_off.data["lat"],drop_off.data["lng"])
    stops=[]
    if data.stops:
        for index, stop in enumerate(data.stops):
            stop_place_id = _extract_place_id(stop, f"stops[{index}]")
            _place_details = await get_place_details(place_id=stop_place_id)
            if _place_details and _place_details.data:
                stops.append((_place_details.data['lat'], _place_details.data['lng']))

    map = maps.get_delivery_route(origin=origin,destination=destination,stops=stops)
    if not map:
        raise HTTPException(status_code=400, detail="Unable to calculate route")

    vehicle = Vehicle[data.vehicleType.value]
    price = calculate_fare_using_vehicle_config_and_distance(
        distance=map.totalDistanceMeters,
        time=map.totalDurationSeconds,
        vehicle=vehicle,
    )
    ride_create= RideCreate(**data.model_dump(),userId=token.userId,price=price,origin=Location(latitude=pick_up.data["lat"],longitude=pick_up.data["lng"]),map=map)

    ride = await add_ride(ride_data=ride_create,payment_service=payment_service)

    return APIResponse(status_code=200,data=ride,detail="Successfully requested for a ride")

@router.patch(
    "/ride/cancel/{rideId}",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role), Depends(check_rider_account_status)],
    response_model=APIResponse[RideOut],
    summary="Cancel a ride",
    description="Cancels a requested ride before it begins.",
)
async def cancel_a_requested_ride_before_ride_has_begun(rideId:str,token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Cancel a ride before it begins.

    Access: Rider only (valid rider access token required).
    """
    canceled_ride = RideUpdate(rideStatus=RideStatus.canceled)
    updated_ride = await update_ride_by_id(ride_id=rideId,rider_id=token.userId,ride_data=canceled_ride)
    return APIResponse(data =updated_ride ,status_code=200,detail="Successfully cancelled ride")


@router.post(
    "/ride/{rideId}/no-driver-decision",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role), Depends(check_rider_account_status)],
    response_model=APIResponse[RideOut],
    summary="Handle no-driver decision",
    description="Lets rider choose to keep searching or cancel when no driver is available at scheduled pickup time.",
)
async def handle_no_driver_decision(
    rideId: str,
    payload: NoDriverDecisionIn,
    token: accessTokenOut = Depends(verify_token_rider_role),
):
    updated_ride = await decide_no_driver_for_ride(
        ride_id=rideId,
        rider_id=token.userId,
        decision=payload.decision,
    )
    return APIResponse(
        data=updated_ride,
        status_code=200,
        detail="No-driver decision recorded successfully",
    )


@router.post(
    "/ride/{rideId}/payment/retry",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role), Depends(check_rider_account_status)],
    response_model=APIResponse[RideOut],
    summary="Retry postpaid payment",
    description="Reopens payment for rides currently in paymentFailed.",
)
async def retry_postpaid_payment(
    rideId: str,
    token: accessTokenOut = Depends(verify_token_rider_role),
):
    updated_ride = await update_ride_by_id(
        ride_id=rideId,
        rider_id=token.userId,
        ride_data=RideUpdate(rideStatus=RideStatus.awaitingPayment),
    )
    return APIResponse(
        data=updated_ride,
        status_code=200,
        detail="Payment retry initiated successfully",
    )
 


@router.get(
    "/ride/{rideId}",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role), Depends(check_rider_account_status)],
    response_model=APIResponse[RideOut],
    summary="Get ride details",
    description="Returns details of a specific ride for the authenticated rider.",
)
async def view_ride_details(rideId:str,token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Get ride details for the authenticated rider.

    Access: Rider only (valid rider access token required).
    """
    
    ride=await retrieve_rides_by_user_id_and_ride_id(user_id=token.userId,ride_id=rideId)
    return APIResponse(data =ride ,status_code=200,detail="Successfully Retrieved ride") 


@router.get(
    "/ride/{rideId}/share",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_rider_role)],
    response_model=APIResponse[RideShareLinkOut],
    summary="Generate ride share link",
    description="Generates a public share link for a specific ride.",
)
async def generate_public_ride_sharing_link(rideId: str, token: accessTokenOut = Depends(verify_token_rider_role)):
    """
    Generate a public share link for a ride.

    Access: Rider only (valid rider access token required).
    """
    payload = await generate_public_ride_sharing_link_for_rider(ride_id=rideId, user_id=token.userId)
    return APIResponse(status_code=200, data=payload, detail="Share link generated")


@router.get(
    "/ride/share/{shareId}",
    response_model_exclude_none=True,
    response_model=APIResponse[RideOut],
    summary="Get shared ride",
    description="Returns ride details using a public share link identifier.",
)
async def get_shared_ride(shareId: str):
    """
    Retrieve ride details using a public share link.

    Access: Public (no auth).
    """
    ride = await retrieve_shared_ride_by_share_id(share_id=shareId)
    return APIResponse(status_code=200, data=ride, detail="Shared ride retrieved")


  
  
# -----------------------------------
# ------- PASSWORD MANAGEMENT ------- 
# -----------------------------------

  

@router.patch(
    "/password-reset",
    dependencies=[Depends(verify_token_rider_role), Depends(check_rider_account_status)],
    summary="Change rider password",
    description="Updates the authenticated rider's password.",
)
async def update_rider_password_while_logged_in(rider_details:RiderUpdatePassword,token:accessTokenOut = Depends(verify_token_rider_role)):
    """
    Change the authenticated rider password.

    Access: Rider only (valid rider access token required).
    """
    driver =  await update_rider_by_id(user_id=token.userId,user_data=rider_details,is_password_getting_changed=True)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")



@router.post(
    "/password-reset/request",
    response_model=APIResponse[ResetPasswordInitiationResponse],
    summary="Request rider password reset",
    description="Initiates the password reset flow by sending an OTP.",
)
async def start_password_reset_process_for_rider_that_forgot_password(rider_details:ResetPasswordInitiation):
    """
    Start the rider password reset flow (send OTP).

    Access: Public (no auth).
    """
    driver =  await rider_reset_password_initiation(rider_details=rider_details)   
    return APIResponse(data = driver,status_code=200,detail="Successfully Sent OTP")



@router.patch(
    "/password-reset/confirm",
    summary="Confirm rider password reset",
    description="Completes password reset with OTP and new password.",
)
async def finish_password_reset_process_for_rider_that_forgot_password(rider_details:ResetPasswordConclusion):
    """
    Complete the rider password reset using an OTP or token.

    Access: Public (no auth).
    """
    driver =  await rider_reset_password_conclusion(rider_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated password")
