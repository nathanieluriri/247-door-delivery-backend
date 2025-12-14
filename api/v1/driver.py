
from fastapi import APIRouter, HTTPException, Query, Request, status, Path,Depends
from typing import List
from schemas.rating import RatingBase, RatingCreate
from schemas.response_schema import APIResponse
from schemas.tokens_schema import accessTokenOut
from schemas.driver import (
    DriverCreate,
    DriverOut,
    DriverBase,
    DriverUpdate,
    DriverRefresh,
)
from services.driver_service import (
    add_driver,
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
router = APIRouter(prefix="/drivers", tags=["Drivers"])

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



@router.get("/" ,response_model_exclude={"data": {"__all__": {"password"}}}, response_model=APIResponse[List[DriverOut]],response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role)])
async def list_drivers(start:int= 0, stop:int=100):
    items = await retrieve_drivers(start=start,stop=stop)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.get("/me", response_model_exclude={"data": {"password"}},response_model=APIResponse[DriverOut],dependencies=[Depends(verify_token_driver_role)],response_model_exclude_none=True)
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


@router.patch("/profile")
async def update_driver_profile(driver_details:DriverUpdate,token:accessTokenOut = Depends(verify_token_driver_role)):
    driver =  await update_driver_by_id(driver_id=token.userId,driver_data=driver_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")
     



@router.delete("/account",dependencies=[Depends(verify_token_driver_role)])
async def delete_user_account(token:accessTokenOut = Depends(verify_token_driver_role)):
    result = await remove_driver(driver_id=token.userId)
    return APIResponse(data=result,status_code=200,detail="Successfully deleted account")



# -------------------------------
# -------RATING MANAGEMENT------- 
# -------------------------------

@router.get("/rating",response_model_exclude={"data": {"__all__": {"password"}}},response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role)])
async def view_rating(token:accessTokenOut = Depends(verify_token_driver_role)):
    rating = await retrieve_rating_by_user_id(user_id=token.userId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.get("/rider/{riderId}/rating",response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role)])
async def view_rider_rating(riderId:str):
    rating = await retrieve_rating_by_user_id(user_id=riderId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.post("/rate/rider", response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role)])
async def rate_rider_after_ride(rating_data:RatingBase,token:accessTokenOut = Depends(verify_token_driver_role)):
    

    
    rider_rating = RatingCreate(**rating_data.model_dump(),raterId=token.userId)
    rating = add_rating(rating_data=rider_rating)
    return APIResponse(data=rating,status_code=200,detail="Successfully Rated Rider")



# -------------------------------
# ------- RIDE MANAGEMENT ------- 
# -------------------------------

@router.get("/ride/history",response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role)])
async def ride_history(token:accessTokenOut = Depends(verify_token_driver_role)):
    rides = await retrieve_rides_by_driver_id(driver_id=token.userId)
    return APIResponse(status_code=200,data= rides, detail="Successfully Retrieved Ride history for driver")

# TODO: Update password routes



# TODO: Create a reusable dependency that checks a user's account status.
# - Use Redis to cache the account status.
# - If the account is active, allow the operation; otherwise, block it.
# - Apply this dependency only to specific endpoints (not globally).
# - Cache results to avoid unnecessary database queries.