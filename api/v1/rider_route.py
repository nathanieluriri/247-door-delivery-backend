import os
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException, Query, Request, status, Path,Depends
from typing import List, Literal, Union
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
from schemas.ride import RideBase, RideCreate, RideOut, RideShareLinkOut, RideUpdate
from schemas.tokens_schema import accessTokenOut
from core.routing_config import maps
from schemas.rider_schema import (
    RiderCreate,
    RiderOut,
    RiderBase,
    RiderUpdate,
    RiderRefresh,
    LoginType,
    RiderUpdatePassword,
)
from repositories.tokens_repo import delete_access_token, delete_refresh_tokens_by_previous_access_token
from security.account_status_checks import check_rider_account_status
from services.address_service import add_address, remove_address, retrieve_address_by_user_id, update_address_by_id
from services.place_service import calculate_fare_using_vehicle_config_and_distance, get_autocomplete, get_place_details, nearby_drivers
from services.rating_service import add_rating, retrieve_rating_by_user_id
from services.ride_service import add_ride, generate_public_ride_sharing_link_for_rider, retrieve_rides_by_user_id, retrieve_rides_by_user_id_and_ride_id, retrieve_shared_ride_by_share_id, update_ride_by_id
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
from dotenv import load_dotenv 
load_dotenv()

router = APIRouter(prefix="/riders", tags=["Riders"])

SUCCESS_PAGE_URL = os.getenv("SUCCESS_PAGE_URL", "http://localhost:8080/success")
ERROR_PAGE_URL   = os.getenv("ERROR_PAGE_URL",   "http://localhost:8080/error")

# --- Step 1: Redirect user to Google login ---
@router.get("/google/auth")
async def login_with_google_account(request: Request):
    if not oauth or not oauth.google:
        raise HTTPException(status_code=500, detail="OAuth configuration not initialized")
    redirect_uri = request.url_for("auth_callback_rider")
    print("REDIRECT URI:", redirect_uri)
 
    return await oauth.google.authorize_redirect(request, redirect_uri)


# --- Step 2: Handle callback from Google ---
@router.get("/auth/callback")
async def auth_callback_rider(request: Request):
    if not oauth or not oauth.google:
        raise HTTPException(status_code=500, detail="OAuth configuration not initialized")
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')

    # Just print or return user info for now
    if user_info:
        print("✅ Google user info:", user_info)
        rider = RiderBase(firstName=user_info['name'],password='',lastName=user_info['given_name'],email=user_info['email'],loginType=LoginType.google)
        data = await authenticate_rider(user_data=rider)
        if data==None:
            new_rider = RiderCreate(**rider.model_dump())
            items = await add_rider(user_data=new_rider)
            
            access_token = items.access_token
            refresh_token = items.refresh_token
            query = urlencode(
                {
                    "status": "success",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                }
            )
            success_url = f"{SUCCESS_PAGE_URL}?{query}"
            response = RedirectResponse(
                url=success_url,
                status_code=status.HTTP_302_FOUND
            )
            return response
        access_token = data.access_token
        refresh_token = data.refresh_token

        query = urlencode(
            {
                "status": "success",
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        )
        success_url = f"{SUCCESS_PAGE_URL}?{query}"
        response = RedirectResponse(
            url=success_url,
            status_code=status.HTTP_302_FOUND
        )
        return response
    else:
        raise HTTPException(status_code=400,detail={"status": "failed", "message": "No user info found"})

@router.get("/",response_model_exclude={"data": {"__all__": {"password"}}}, response_model=APIResponse[List[RiderOut]],response_model_exclude_none=True,dependencies=[Depends(verify_token)])
async def list_riders(start:int= 0, stop:int=100):
    items = await retrieve_riders(start=start,stop=stop)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")

@router.get("/profile", response_model_exclude={"data": {"password"}},response_model=APIResponse[RiderOut],dependencies=[Depends(verify_token_rider_role)],response_model_exclude_none=True)
async def get_my_rider_details(token:accessTokenOut = Depends(verify_token_rider_role)):
    items = await retrieve_rider_by_rider_id(id=token.userId)
    return APIResponse(status_code=200, data=items, detail="users items fetched")

 


@router.post("/signup", response_model_exclude={"data": {"password"}},response_model=APIResponse[RiderOut])
async def signup_new_rider(user_data:RiderBase):
    new_rider = RiderCreate(**user_data.model_dump())
    items = await add_rider(user_data=new_rider)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.post("/login",response_model_exclude={"data": {"password"}}, response_model=APIResponse[RiderOut])
async def login_rider(user_data:RiderBase):
    items = await authenticate_rider(user_data=user_data)
   
     
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.post("/refresh",response_model_exclude={"data": {"password"}},response_model=APIResponse[RiderOut],dependencies=[Depends(verify_token_to_refresh)])
async def refresh_rider_tokens(user_data:RiderRefresh,token:accessTokenOut = Depends(verify_token_to_refresh)):
    
    items= await refresh_rider_tokens_reduce_number_of_logins(user_refresh_data=user_data,expired_access_token=token.accesstoken)

    return APIResponse(status_code=200, data=items, detail="users items fetched")


@router.delete("/account",dependencies=[Depends(verify_token_rider_role)])
async def delete_rider_account(token:accessTokenOut = Depends(verify_token_rider_role)):
    result = await remove_rider(user_id=token.userId)
    return result

@router.post("/logout", dependencies=[Depends(verify_token_rider_role)])
async def logout_rider(token: accessTokenOut = Depends(verify_token_rider_role)):
    if not token.accesstoken:
        raise HTTPException(status_code=400, detail="Invalid access token")
    await delete_refresh_tokens_by_previous_access_token(accessToken=token.accesstoken)
    deleted = await delete_access_token(accessToken=token.accesstoken)
    if not deleted:
        raise HTTPException(status_code=400, detail="Access token already invalidated")
    return APIResponse(status_code=200, data=True, detail="Logged out successfully")

@router.patch("/profile")
async def update_rider_profile(rider_details:RiderUpdate,token:accessTokenOut = Depends(verify_token_rider_role)):
    rider = await update_rider_by_id(user_id=token.userId,user_data=rider_details)
    return APIResponse(data=rider,detail="Rider Profile updated successfully", status_code=200)

# -------------------------------
# -------RATING MANAGEMENT------- 
# -------------------------------


@router.get("/rating",response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)])
async def view_rating(token:accessTokenOut = Depends(verify_token_rider_role)):
    rating = await retrieve_rating_by_user_id(user_id=token.userId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.get("/driver/{driverId}/rating",response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)])
async def view_driver_rating(driverId:str):
    rating = await retrieve_rating_by_user_id(user_id=driverId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.post("/rate/driver", response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)])
async def rate_driver_after_ride(rating_data:RatingBase,token:accessTokenOut = Depends(verify_token_rider_role)):
    
    rider_rating = RatingCreate(**rating_data.model_dump(),raterId=token.userId)
    rating = await add_rating(rating_data=rider_rating)
    return APIResponse(data=rating,status_code=200,detail="Successfully Rated Driver")




# --------------------------------
# -------ADDRESS MANAGEMENT------- 
# --------------------------------

@router.get("/addresses",response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[List[AddressOut]])
async def view_all_previous_addresses_created_by_user(token:accessTokenOut = Depends(verify_token_rider_role)):
    
    address = await retrieve_address_by_user_id(userId=token.userId)
    return APIResponse(data=address,status_code=200,detail="Successfully retrieved Addresses")

@router.post("/address", response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[AddressOut])
async def create_new_address_for_a_user(address_data:AddressBase,token:accessTokenOut = Depends(verify_token_rider_role)):
 
    new_address_data = AddressCreate(**address_data.model_dump(),userId=token.userId)
    address = await add_address(address_data=new_address_data)
    return APIResponse(data = address,status_code=200,detail="Successfully created new Address")


@router.delete("/address/{addressId}", response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[Literal[True]])
async def delete_address_detials_using_address_id(addressId:str,token:accessTokenOut = Depends(verify_token_rider_role)):
    
    removed_address = await remove_address(address_id=addressId,user_id=token.userId)
    return APIResponse(data=removed_address,detail="Successfully deleted Address",status_code= 200)



@router.patch("/address/{addressId}", response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[AddressOut])
async def update_address_label(addressId:str,address_data:AddressUpdate,token:accessTokenOut = Depends(verify_token_rider_role)):
     
    address = await update_address_by_id(address_id=addressId,address_data=address_data,user_id=token.userId)
    return APIResponse(data=address,status_code=200,detail = "Successfully updated addres")


# -------------------------------
# ------- PLACES MANAGEMENT ------- 
# -------------------------------
@router.get(
    "/place/allowedCountries",
    response_model=APIResponse[List[str]],
    summary="Get location suggestions (cached for 14 days)",
)
async def autocomplete_route(
    input: str = Query(..., description="User input text for autocomplete"),
    country: ALLOWED_COUNTRIES = Query(..., description="Choose one of them ")
):
    """Return location autocomplete suggestions."""
    return APIResponse(data=ALLOWED_COUNTRIES,details="Allowed Countries Retrieved",status_code=200)


@router.get(
    "/place/autocomplete",
    response_model=APIResponse[Union[List[PlaceBase],None]],
    summary="Get location suggestions (cached for 14 days)",
)
async def autocomplete(
    input: str = Query(..., description="User input text for autocomplete"),
    country: ALLOWED_COUNTRIES = Query(..., description="Choose one of them ")
):
    """Return location autocomplete suggestions."""
    return await get_autocomplete(input, country)



@router.get(
    "/place/details",
     
    summary="Get place details (cached for 14 days)",
)
async def place_details(
    place_id: str = Query(..., description="Google Place ID")
):
    """Return full details for a given place."""
    return await get_place_details(place_id)



@router.post(
    "/place/calculate-fare",
    summary="Use place id for pickup, destination & stops to calculate fair price return distance, eta and fare price ",
    response_model=APIResponse[FareBetweenPlacesCalculationResponse]
)
async def calculate_fare_price(data:FareBetweenPlacesCalculationRequest):
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

@router.get("/ride/history" ,response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[List[RideOut]])
async def ride_history(token:accessTokenOut = Depends(verify_token_rider_role)):
    rides = await retrieve_rides_by_user_id(user_id=token.userId)
    return APIResponse(data = rides, status_code=200, detail = "Successfully retrieved Ride history")

 
@router.post("/ride/request",  response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[RideOut])
async def requesting_a_new_ride_or_delivery_request(data:RideBase,token:accessTokenOut = Depends(verify_token_rider_role),payment_service: PaymentService = Depends(get_payment_service)):

    pick_up = await get_place_details(place_id=data.pickup)
    drop_off = await get_place_details(place_id=data.destination)
   
    if not pick_up or not pick_up.data:
        raise HTTPException(status_code=400, detail="Invalid pickup location")
    if not drop_off or not drop_off.data:
        raise HTTPException(status_code=400, detail="Invalid destination location")
    
    origin = (pick_up.data["lat"],pick_up.data["lng"])
    
    available_drivers = await nearby_drivers(pickup_lat=pick_up.data["lat"],pickup_lon=pick_up.data["lng"])
    
    pickup_schedule = data.pickupSchedule or 0
    if (available_drivers>0 and pickup_schedule==0) or (pickup_schedule and pickup_schedule>=240):
        destination = (drop_off.data["lat"],drop_off.data["lng"])
        stops=[]
        if data.stops:
            index=0
            for stop in data.stops:
                _place_details = await get_place_details(place_id=stop)
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
    else:
        raise HTTPException(status_code=404,detail="No Driver's available within 5km radius for pickup at this moment")

@router.patch("/ride/cancel/{rideId}",  response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role),Depends(check_rider_account_status)],response_model=APIResponse[RideOut])
async def cancel_a_requested_ride_before_ride_has_begun(rideId:str,token:accessTokenOut = Depends(verify_token_rider_role)):
    canceled_ride = RideUpdate(rideStatus=RideStatus.canceled)
    updated_ride = await update_ride_by_id(ride_id=rideId,rider_id=token.userId,ride_data=canceled_ride)
    return APIResponse(data =updated_ride ,status_code=200,detail="Successfully cancelled ride")
 


@router.get("/ride/{rideId}",  response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role),Depends(check_rider_account_status)],response_model=APIResponse[RideOut])
async def view_ride_details(rideId:str,token:accessTokenOut = Depends(verify_token_rider_role)):
    
    ride=await retrieve_rides_by_user_id_and_ride_id(user_id=token.userId,ride_id=rideId)
    return APIResponse(data =ride ,status_code=200,detail="Successfully Retrieved ride") 


@router.get("/ride/{rideId}/share", response_model_exclude_none=True, dependencies=[Depends(verify_token_rider_role)], response_model=APIResponse[RideShareLinkOut])
async def generate_public_ride_sharing_link(rideId: str, token: accessTokenOut = Depends(verify_token_rider_role)):
    payload = await generate_public_ride_sharing_link_for_rider(ride_id=rideId, user_id=token.userId)
    return APIResponse(status_code=200, data=payload, detail="Share link generated")


@router.get("/ride/share/{shareId}", response_model_exclude_none=True, response_model=APIResponse[RideOut])
async def get_shared_ride(shareId: str):
    ride = await retrieve_shared_ride_by_share_id(share_id=shareId)
    return APIResponse(status_code=200, data=ride, detail="Shared ride retrieved")


  
  
# -----------------------------------
# ------- PASSWORD MANAGEMENT ------- 
# -----------------------------------

  

@router.patch("/password-reset",dependencies=[Depends(verify_token_rider_role),Depends(check_rider_account_status)])
async def update_rider_password_while_logged_in(rider_details:RiderUpdatePassword,token:accessTokenOut = Depends(verify_token_rider_role)):
    driver =  await update_rider_by_id(user_id=token.userId,user_data=rider_details,is_password_getting_changed=True)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")



@router.post("/password-reset/request",response_model=APIResponse[ResetPasswordInitiationResponse] )
async def start_password_reset_process_for_rider_that_forgot_password(rider_details:ResetPasswordInitiation):
    driver =  await rider_reset_password_initiation(rider_details=rider_details)   
    return APIResponse(data = driver,status_code=200,detail="Successfully Sent OTP")



@router.patch("/password-reset/confirm")
async def finish_password_reset_process_for_rider_that_forgot_password(rider_details:ResetPasswordConclusion):
    driver =  await rider_reset_password_conclusion(rider_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated password")
