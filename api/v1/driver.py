
import json
from fastapi import APIRouter, HTTPException, Query, Request, status, Path,Depends
from typing import List, Optional

from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from schemas.imports import ResetPasswordConclusion, ResetPasswordInitiation, ResetPasswordInitiationResponse
from schemas.rating import RatingBase, RatingCreate
from schemas.response_schema import APIResponse
from core.redis_cache import async_redis
from schemas.tokens_schema import accessTokenOut
from schemas.payout import (
    PayoutCreate,
    PayoutOut,
    PayoutBase,
    PayoutUpdate,
)
from services.payout_service import (
    add_payout,
    remove_payout,
    retrieve_payouts,
    retrieve_payout_by_payout_id,
    update_payout_by_id,
)

from schemas.driver import (
    DriverCreate,
    DriverOut,
    DriverBase,
    DriverUpdate,
    DriverRefresh,
    DriverUpdatePassword,
)
from security.account_status_checks import check_driver_account_status
from services.driver_service import (
    add_driver,
    driver_reset_password_conclusion,
    driver_reset_password_intiation,
    remove_driver,
    retrieve_drivers,
    authenticate_driver,
    retrieve_driver_by_driver_id,
    update_driver,
    update_driver_by_id,
    refresh_driver_tokens_reduce_number_of_logins,
    oauth

)
from security.auth import verify_any_token,verify_token_to_refresh,verify_token_driver_role
from services.rating_service import add_rating, retrieve_rating_by_user_id
from services.ride_service import retrieve_rides_by_driver_id
import asyncio


router = APIRouter(prefix="/drivers", tags=["Drivers"])
# simple in-memory subscribers store
driver_subscribers: set[asyncio.Queue] = set()
# --- Step 1: Redirect user to Google login ---
@router.get("/google/auth")
async def login(request: Request):
    base_url = request.url_for("root")
    redirect_uri = f"{base_url}auth/callback"
     
    return await oauth.google_driver.authorize_redirect(request, redirect_uri)


# --- Step 2: Handle callback from Google ---
@router.get("/auth/callback",response_model_exclude={"data": {"password"}},response_model=APIResponse[DriverOut])
async def auth_callback(request: Request):
    try:
        token = await oauth.google_driver.authorize_access_token(request)
        user_info = token.get('userinfo')
    except:
        raise HTTPException(status_code=400,detail="Login session expired or was invalid. Please try logging in again.")
    # Just print or return user info for now
    if user_info:
        new_data= DriverCreate(email=user_info["email"],password="",)
        old_data= DriverBase(email=user_info["email"],password="",)
        try:
            driver= await add_driver(driver_data=new_data)
        except:
            
           driver= await authenticate_driver(user_data=old_data)
        # user_info.get("email_verified",False)
        # user_info.get("given_name",None)
        # user_info.get("family_name",None)
        # user_info.get("picture",None)
        return APIResponse(status_code=200,detail="Successful Login",data=driver)
    else:
        raise HTTPException(status_code=400,detail={"status": "failed", "message": "No user info found"})



@router.get("/" ,response_model_exclude={"data": {"__all__": {"password"}}}, response_model=APIResponse[List[DriverOut]],response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def list_drivers(start:int= 0, stop:int=100):
    items = await retrieve_drivers(start=start,stop=stop)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.get("/me", response_model_exclude={"data": {"password"}},response_model=APIResponse[DriverOut],dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)],response_model_exclude_none=True)
async def get_driver_details(token:accessTokenOut = Depends(verify_any_token)):
 
    try:
        items = await retrieve_driver_by_driver_id(id=token.userId)
        return APIResponse(status_code=200, data=items, detail="users items fetched")
    except Exception as e:
        if str(e) == "'JWTPayload' object has no attribute 'userId'":
            raise HTTPException(status_code=401,detail=f"Invalid Token Use Driver Id if you want to access driver details with these tokens")
        raise HTTPException(status_code=500,detail=f"{e}")
     
@router.post("/signup", response_model_exclude={"data": {"password"}},response_model=APIResponse[DriverOut])
async def signup_new_driver(user_data:DriverBase):
    if len(user_data.password)<8:
        raise HTTPException(status_code=401,detail="Password too short")
    new_user = DriverCreate(**user_data.model_dump())
    items = await add_driver(driver_data=new_user)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.post("/login",response_model_exclude={"data": {"password"}}, response_model=APIResponse[DriverOut])
async def login_driver(user_data:DriverBase):
    if len(user_data.password)<8:
        raise HTTPException(status_code=401,detail="Password too short")
    items = await authenticate_driver(user_data=user_data)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")



@router.post("/refesh",response_model_exclude={"data": {"password"}},response_model=APIResponse[DriverOut],dependencies=[Depends(verify_token_to_refresh)])
async def refresh_driver_tokens(user_data:DriverRefresh,token:accessTokenOut = Depends(verify_token_to_refresh)):
    
    items= await refresh_driver_tokens_reduce_number_of_logins(user_refresh_data=user_data,expired_access_token=token.accesstoken)

    return APIResponse(status_code=200, data=items, detail="users items fetched")


@router.patch("/profile",dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def update_driver_profile(driver_details:DriverUpdate,token:accessTokenOut = Depends(verify_token_driver_role)):
    driver =  await update_driver_by_id(driver_id=token.userId,driver_data=driver_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")
     



@router.delete("/account",dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def delete_user_account(token:accessTokenOut = Depends(verify_token_driver_role)):
    result = await remove_driver(driver_id=token.userId)
    return APIResponse(data=result,status_code=200,detail="Successfully deleted account")



# -------------------------------
# -------RATING MANAGEMENT------- 
# -------------------------------

@router.get("/rating",response_model_exclude={"data": {"__all__": {"password"}}},response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def view_rating(token:accessTokenOut = Depends(verify_token_driver_role)):
    rating = await retrieve_rating_by_user_id(user_id=token.userId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.get("/rider/{riderId}/rating",response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def view_rider_rating(riderId:str):
    rating = await retrieve_rating_by_user_id(user_id=riderId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.post("/rate/rider", response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def rate_rider_after_ride(rating_data:RatingBase,token:accessTokenOut = Depends(verify_token_driver_role)):
    

    
    rider_rating = RatingCreate(**rating_data.model_dump(),raterId=token.userId)
    rating = add_rating(rating_data=rider_rating)
    return APIResponse(data=rating,status_code=200,detail="Successfully Rated Rider")



# -------------------------------
# ------- RIDE MANAGEMENT ------- 
# -------------------------------


@router.get(
    "/ride/events",
    response_model_exclude={"data": {"password"}},
    
    dependencies=[Depends(verify_token_driver_role)],
    summary="Subscribe to ride events for drivers",
    description=(
        "Establishes a Server-Sent Events (SSE) connection for the authenticated driver. "
        "The driver will receive both global ride notifications and private notifications "
        "targeted specifically to them."
    )
)
async def subscribe_to_events(
    request: Request,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    SSE endpoint for drivers to receive ride notifications.

    - Global channel 'drivers:all' → broadcasts to all drivers
    - Private channel 'driver:{userId}:events' → private messages to the driver
    """
    pubsub = async_redis.pubsub()
    await pubsub.subscribe(
        "drivers:all",                 # global notifications
        f"driver:{token.userId}:events"  # private notifications
    )

    async def event_generator():
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break

                if message["type"] == "message":
                    yield f"data: {message['data']}\n\n"
        finally:
            await pubsub.unsubscribe(
                "drivers:all",
                f"driver:{token.userId}:events"
            )
            await pubsub.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
    

@router.post("/ride/{ride_id}/accept")
async def accept_ride(
    ride_id: str,
    token: accessTokenOut = Depends(verify_token_driver_role), 
):
    # TODO: WORK ON THIS
    pass
    
    
@router.post("/ride/{ride_id}")
async def retrieve_ride_details(
    ride_id: str,
    token: accessTokenOut = Depends(verify_token_driver_role), 
):
    # TODO: WORK ON THIS
    pass

@router.get("/ride/history",response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def ride_history(token:accessTokenOut = Depends(verify_token_driver_role)):
    rides = await retrieve_rides_by_driver_id(driver_id=token.userId)
    return APIResponse(status_code=200,data= rides, detail="Successfully Retrieved Ride history for driver")

 
 
# -----------------------------------
# ------- PASSWORD MANAGEMENT ------- 
# -----------------------------------

 
@router.patch("/password-reset",dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def update_driver_password_while_logged_in(driver_details:DriverUpdatePassword,token:accessTokenOut = Depends(verify_token_driver_role)):
    driver =  await update_driver_by_id(driver_id=token.userId,driver_data=driver_details,is_password_getting_changed=True)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")



@router.post("/password-reset/request",response_model=APIResponse[ResetPasswordInitiationResponse] )
async def start_password_reset_process_for_driver_that_forgot_password(driver_details:ResetPasswordInitiation):
    driver =  await driver_reset_password_intiation(driver_details=driver_details)   
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")



@router.patch("/password-reset/confirm")
async def finish_password_reset_process_for_driver_that_forgot_password(driver_details:ResetPasswordConclusion):
    driver =  await driver_reset_password_conclusion(driver_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")




# ---------------------------------
# ------- PAYOUT MANAGEMENT ------- 
# ---------------------------------






# ------------------------------
# List Payouts (with pagination )
# ------------------------------
@router.get("/payouts", response_model=APIResponse[List[PayoutOut]])
async def list_previous_payouts(
    start: Optional[int] = Query(None, description="Start index for range-based pagination"),
    stop: Optional[int] = Query(None, description="Stop index for range-based pagination"),
    page_number: Optional[int] = Query(None, description="Page number for page-based pagination (0-indexed)"),
 
):
    """
    Retrieves a list of Payouts with pagination and optional filtering.
    - Priority 1: Range-based (start/stop)
    - Priority 2: Page-based (page_number)
    - Priority 3: Default (first 100)
    """
    PAGE_SIZE = 50
    parsed_filters = {}
    # TODO: WORK ON THIS
     

    # 2. Determine Pagination
    # Case 1: Prefer start/stop if provided
    if start is not None or stop is not None:
        if start is None or stop is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both 'start' and 'stop' must be provided together.")
        if stop < start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'stop' cannot be less than 'start'.")
        
        # Pass filters to the service layer
        items = await retrieve_payouts(filters=parsed_filters, start=start, stop=stop)
        return APIResponse(status_code=200, data=items, detail="Fetched successfully")

    # Case 2: Use page_number if provided
    elif page_number is not None:
        if page_number < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'page_number' cannot be negative.")
        
        start_index = page_number * PAGE_SIZE
        stop_index = start_index + PAGE_SIZE
        # Pass filters to the service layer
        items = await retrieve_payouts(filters=parsed_filters, start=start_index, stop=stop_index)
        return APIResponse(status_code=200, data=items, detail=f"Fetched page {page_number} successfully")

    # Case 3: Default (no params)
    else:
        # Pass filters to the service layer
        items = await retrieve_payouts(filters=parsed_filters, start=0, stop=100)
        detail_msg = "Fetched first 100 records successfully"
        if parsed_filters:
            # If filters were applied, adjust the detail message
            detail_msg = f"Fetched first 100 records successfully (with filters applied)"
        return APIResponse(status_code=200, data=items, detail=detail_msg)


# ------------------------------
# Retrieve a single Payout
# ------------------------------
@router.get("/payout/{id}", response_model=APIResponse[PayoutOut])
async def view_information_regarding_a_previous_payout(
    id: str = Path(..., description="payout ID to fetch specific item")
):
    """
    Retrieves a single Payout by its ID.
    """
    # TODO: WORK ON THIS
    item = await retrieve_payout_by_payout_id(id=id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payout not found")
    return APIResponse(status_code=200, data=item, detail="payout item fetched")



# ------------------------------
# Retrieve a single Payout
# ------------------------------
@router.get("/payout", response_model=APIResponse[PayoutOut])
async def view_information_regarding_available_withdrawal_option(
    id: str = Path(..., description="payout ID to fetch specific item")
):
    """
    Retrieves a single Payout by its ID.
    """
    # TODO: WORK ON THIS
    item = await retrieve_payout_by_payout_id(id=id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payout not found")
    return APIResponse(status_code=200, data=item, detail="payout item fetched")


# ------------------------------
# Create a new Payout
# ------------------------------
# Uses PayoutBase for input (correctly)
@router.post("/payout", response_model=APIResponse[PayoutOut], status_code=status.HTTP_201_CREATED)
async def withdraw_money_from_247earnings_by_creating_a_payout(payload: PayoutBase):
    """
    Creates a new Payout.
    """
    # TODO: WORK ON THIS
    # Creates PayoutCreate object which includes date_created/last_updated
    new_data = PayoutCreate(**payload.model_dump()) 
    new_item = await add_payout(new_data)
    if not new_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create payout")
    
    return APIResponse(status_code=201, data=new_item, detail=f"Payout created successfully")





# class DriverIdPayload(BaseModel):
#     driver_id: str = None  # optional for broadcast

# # ------------------------------
# # 1️⃣ Test route: broadcast to all drivers
# # ------------------------------
# @router.post("/test/notify_all")
# async def test_notify_all():
#     """
#     Broadcast a test ride event to all drivers with hardcoded data.
#     """
#     message = {
#         "event": "ride_request",
#         "ride_id": "test_ride_001",
#         "pickup": "Test Pickup",
#         "destination": "Test Destination",
#         "fare": 1000
#     }

#     await async_redis.publish("drivers:all", json.dumps(message))
#     return {"status": "success", "message": "Event sent to all drivers"}

# # ------------------------------
# # 2️⃣ Test route: send to a specific driver
# # ------------------------------
# @router.post("/test/notify_driver")
# async def test_notify_driver(payload: DriverIdPayload):
#     """
#     Send a test ride event to a specific driver with hardcoded data.
#     """
#     if not payload.driver_id:
#         raise HTTPException(status_code=400, detail="driver_id is required")

#     message = {
#         "event": "ride_request",
#         "ride_id": "test_ride_002",
#         "pickup": "Test Pickup",
#         "destination": "Test Destination",
#         "fare": 1000
#     }

#     await async_redis.publish(f"driver:{payload.driver_id}:events", json.dumps(message))
#     return {"status": "success", "message": f"Event sent to driver {payload.driver_id}"}