
from fastapi import APIRouter, HTTPException, Query, Request, status, Path,Depends
from typing import List, Literal, Union
from core.countries import ALLOWED_COUNTRIES
from core.payements import PaymentService, get_payment_service
from core.vehicles import Vehicle
from core.vehicles_config import VehicleType
from schemas.address import AddressBase, AddressCreate, AddressOut, AddressUpdate
from schemas.imports import RideStatus
from schemas.place import FareBetweenPlacesCalculationRequest, FareBetweenPlacesCalculationResponse, Location, PlaceBase
from schemas.rating import RatingBase, RatingCreate
from schemas.response_schema import APIResponse
from schemas.ride import RideBase, RideCreate, RideOut, RideUpdate
from schemas.tokens_schema import accessTokenOut
from core.routing_config import maps
from schemas.rider_schema import (
    RiderCreate,
    RiderOut,
    RiderBase,
    RiderUpdate,
    RiderRefresh,
)
from services.address_service import add_address, remove_address, retrieve_address_by_user_id, update_address_by_id
from services.place_service import calculate_fare_using_vehicle_config_and_distance, get_autocomplete, get_place_details
from services.rating_service import add_rating, retrieve_rating_by_user_id
from services.ride_service import add_ride, retrieve_ride_by_user_id, retrieve_ride_by_user_id_and_ride_id, update_ride_by_id
from services.rider_service import (
    add_rider,
    remove_rider,
    retrieve_riders,
    authenticate_rider,
    retrieve_rider_by_rider_id,
    update_rider_by_id,
    refresh_rider_tokens_reduce_number_of_logins,
    oauth
)
from security.auth import verify_token,verify_token_to_refresh, verify_token_rider_role
router = APIRouter(prefix="/users", tags=["Riders"])
# --- Step 1: Redirect user to Google login ---
@router.get("/google/auth")
async def login_with_google_account(request: Request):
    base_url = request.url_for("root")
    redirect_uri = f"{base_url}auth/callback"
    print(redirect_uri)
    return await oauth.google.authorize_redirect(request, redirect_uri)


# --- Step 2: Handle callback from Google ---
@router.get("/auth/callback")
async def auth_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')

    # Just print or return user info for now
    if user_info:
        print("✅ Google user info:", user_info)
        return APIResponse(status_code=200,detail="Successful Login",data={"status": "success", "user": user_info})
    else:
        raise HTTPException(status_code=400,detail={"status": "failed", "message": "No user info found"})

@router.get("/",response_model_exclude={"data": {"__all__": {"password"}}}, response_model=APIResponse[List[RiderOut]],response_model_exclude_none=True,dependencies=[Depends(verify_token)])
async def list_riders(start:int= 0, stop:int=100):
    items = await retrieve_riders(start=0,stop=100)
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


@router.post("/refesh",response_model_exclude={"data": {"password"}},response_model=APIResponse[RiderOut],dependencies=[Depends(verify_token_to_refresh)])
async def refresh_rider_tokens(user_data:RiderRefresh,token:accessTokenOut = Depends(verify_token_to_refresh)):
    
    items= await refresh_rider_tokens_reduce_number_of_logins(user_refresh_data=user_data,expired_access_token=token.accesstoken)

    return APIResponse(status_code=200, data=items, detail="users items fetched")


@router.delete("/account",dependencies=[Depends(verify_token_rider_role)])
async def delete_rider_account(token:accessTokenOut = Depends(verify_token_rider_role)):
    result = await remove_rider(user_id=token.userId)
    return result

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

@router.post("/rate/driver/{rideId}", response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)])
async def rate_driver_after_ride(rating_data:RatingBase):
    # TODO: ADD USER VERIFICATION IN THE SERVICE FUNCTION
    rider_rating = RatingCreate(**rating_data.model_dump())
    rating = add_rating(rating_data=rider_rating)
    
    return APIResponse(data=rating,status_code=200,detail="Successfully Rated Driver")




# --------------------------------
# -------ADDRESS MANAGEMENT------- 
# --------------------------------

@router.get("/addresses",response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[List[AddressOut]])
async def view_all_previous_addresses_created_by_user(token:accessTokenOut = Depends(verify_token_rider_role)):
    
    address = await retrieve_address_by_user_id(userId=token.userId)
    return APIResponse(data=address,status_code=200,detail="Successfully retrieved Addresses")

@router.post("/address", response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[AddressOut])
async def create_new_address_for_a_user(address_data:AddressBase):
    # TODO: ADD USER 
    new_address_data = AddressCreate(**address.model_dump())
    address = await add_address(address_data=new_address_data)
    return APIResponse(data = address,status_code=200,detail="Successfully created new Address")


@router.delete("/address/{addressId}", response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[Literal[True]])
async def delete_address_detials_using_address_id(addressId:str):
    # TODO: ADD USER VERIFICATION IN THE SERVICE FUNCTION
    removed_address = await remove_address(address_id=addressId)
    return APIResponse(data=removed_address,detail="Successfully deleted Address",status_code= 200)



@router.patch("/address/{addressId}", response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[AddressOut])
async def update_address_label(addressId:str,address_data:AddressUpdate):
    # TODO: ADD USER VERIFICATION IN THE SERVICE FUNCTION
    address = await update_address_by_id(address_id=addressId,address_data=address_data)
    return APIResponse(data=address,status_code=200,detail = "Successfully updated addres")


# -------------------------------
# ------- PLACES MANAGEMENT ------- 
# -------------------------------
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
   
    origin = (pick_up.data["lat"],pick_up.data["lng"])
    destination = (drop_off.data["lat"],drop_off.data["lng"])
    stops=None
    if data.stops:
        stops=[]
        index=0
        for stop in data.stops:
            _place_details =await get_place_details(place_id=stop)
            stops.append((_place_details.data['lat'],_place_details.data['lng']))
    
    map = maps.get_delivery_route(origin=origin,destination=destination,stops=stops)
    
    bike_calculation = calculate_fare_using_vehicle_config_and_distance(distance=map.totalDistanceMeters,time=map.totalDurationSeconds,vehicle=Vehicle.MOTOR_BIKE,)
    car_calculation = calculate_fare_using_vehicle_config_and_distance(distance=map.totalDistanceMeters,time=map.totalDurationSeconds,vehicle=Vehicle.CAR,)
    fare = FareBetweenPlacesCalculationResponse(origin=Location(latitude=pick_up.data["lat"],longitude=pick_up.data["lng"]),bike_fare=bike_calculation,car_fare=car_calculation,map=map)
    
    return APIResponse(status_code=200,detail="Successfully calculated far",data= fare)

# -------------------------------
# ------- RIDE MANAGEMENT ------- 
# -------------------------------

@router.get("/ride/history" ,response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[List[RideOut]])
async def ride_history(token:accessTokenOut = Depends(verify_token_rider_role)):
    rides = await retrieve_ride_by_user_id(user_id=token.userId)
    return APIResponse(data = rides, status_code=200, detail = "Successfully retrieved Ride history")

 
@router.post("/ride/request",  response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[RideOut])
async def requesting_a_new_ride_or_delivery_request(data:RideBase,token:accessTokenOut = Depends(verify_token_rider_role),payment_service: PaymentService = Depends(get_payment_service)):

    pick_up = await get_place_details(place_id=data.pickup)
    drop_off = await get_place_details(place_id=data.destination)
   
    origin = (pick_up.data["lat"],pick_up.data["lng"])
    destination = (drop_off.data["lat"],drop_off.data["lng"])
    stops=None
    if data.stops:
        stops=[]
        index=0
        for stop in data.stops:
            _place_details =await get_place_details(place_id=stop)
            stops.append((_place_details.data['lat'],_place_details.data['lng']))
    
    map = maps.get_delivery_route(origin=origin,destination=destination,stops=stops)
    
    
    vehicle = Vehicle[data.vehicleType.value]
    price = calculate_fare_using_vehicle_config_and_distance(
        distance=map.totalDistanceMeters,
        time=map.totalDurationSeconds,
        vehicle=vehicle,
    )
    ride_create= RideCreate(**data.model_dump(),userId=token.userId,price=price,origin=Location(latitude=pick_up.data["lat"],longitude=pick_up.data["lng"]),map=map)
    
    ride = await add_ride(ride_data=ride_create,payment_service=payment_service)
    
    return APIResponse(status_code=200,data=ride,detail="Successfully requested for a ride")


@router.patch("/ride/cancel/{rideId}",  response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[RideOut])
async def cancel_a_requested_ride_before_ride_has_begun(rideId:str,token:accessTokenOut = Depends(verify_token_rider_role)):
    canceled_ride = RideUpdate(rideStatus=RideStatus.canceled)
    updated_ride = await update_ride_by_id(ride_id=rideId,rider_id=token.userId,ride_data=canceled_ride)
    return APIResponse(data =updated_ride ,status_code=200,detail="Successfully cancelled ride")
 


@router.get("/ride/{rideId}",  response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[RideOut])
async def view_ride_details(rideId:str,token:accessTokenOut = Depends(verify_token_rider_role)):
    
    ride=await retrieve_ride_by_user_id_and_ride_id(user_id=token.userId,ride_id=rideId)
    return APIResponse(data =ride ,status_code=200,detail="Successfully Retrieved ride") 


@router.get("/ride/{rideId}/share",  response_model_exclude_none=True,dependencies=[Depends(verify_token_rider_role)],response_model=APIResponse[RideOut])
async def generate_public_ride_sharing_link(rideId:str):
    # TODO: IMPLEMENT THIS ROUTE FUNCTION
    pass


