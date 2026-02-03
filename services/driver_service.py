# ============================================================================
# DRIVER SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-03 10:19:30 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

import os
from bson import ObjectId
from fastapi import HTTPException
from bson.errors import InvalidId
from typing import List, Union

from repositories.reset_token import(
    create_reset_token,
    get_reset_token,
 
    ResetTokenCreate,
 
    ResetTokenBase,
    UserType,
    generate_otp,
)
from repositories.driver import (
    create_driver,
    get_driver,
    get_drivers,
    update_driver,
    delete_driver,
)
from repositories.tokens_repo import add_access_tokens, add_refresh_tokens, delete_access_token, delete_refresh_token, get_refresh_tokens
from schemas.driver import (
    DriverBase,
    DriverCreate,
    DriverRefresh,
    DriverUpdate,
    DriverOut,
    DriverUpdatePassword,
    DriverUpdateAccountStatus,
    DriverLocationUpdate,
    DriverUpdateProfile,
    DriverVehicleUpdate,
)
from schemas.imports import ALLOWED_ACCOUNT_STATUS_TRANSITIONS, AccountStatus, ResetPasswordConclusion, ResetPasswordInitiation, ResetPasswordInitiationResponse
from schemas.tokens_schema import accessTokenCreate, refreshTokenCreate
from security.encrypting_jwt import  create_jwt_token
from security.hash import check_password
from authlib.integrations.starlette_client import OAuth

from services.email_service import send_ban_warning, send_otp
from services.sse_service import (
    publish_ride_request,
    publish_ride_request_to_driver,
    update_driver_presence,
)
from services.background_check_service import ensure_background_record, fetch_background_check

oauth = OAuth()
oauth.register(
    name='google_driver',
    client_id=os.getenv("GOOGLE_CLIENT_ID_FOR_DRIVER_ROLE"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET_FOR_DRIVER_ROLE"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

async def add_driver(driver_data: DriverCreate) -> DriverOut:
    """adds an entry of DriverCreate to the database and returns an object

    Returns:
        _type_: DriverOut
    """
    user =  await get_driver(filter_dict={"email":driver_data.email.lower()})
    if user==None:
        new_driver= await create_driver(driver_data=driver_data)
        await ensure_background_record(new_driver.id)
        access_token = await add_access_tokens(token_data=accessTokenCreate(userId=new_driver.id))
        refresh_token  = await add_refresh_tokens(token_data=refreshTokenCreate(userId=new_driver.id,previousAccessToken=access_token.accesstoken))
        token_activation = new_driver.accountStatus==AccountStatus.ACTIVE
        token = create_jwt_token(access_token=access_token.accesstoken,user_id=new_driver.id,user_type="DRIVER",is_activated=token_activation)
        new_driver.password = ""
        new_driver.access_token= token
        new_driver.refresh_token = refresh_token.refreshtoken
        return new_driver
    else:
        raise HTTPException(status_code=409,detail="Driver Already exists")


async def remove_driver(driver_id: str):
    """deletes a field from the database and removes DriverCreateobject 

    Raises:
        HTTPException 400: Invalid driver ID format
        HTTPException 404:  Driver not found
    """
    if not ObjectId.is_valid(driver_id):
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    filter_dict = {"_id": ObjectId(driver_id)}
    result = await delete_driver(filter_dict)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Driver not found")

    else: return True
    
async def retrieve_driver_by_driver_id(id: str) -> DriverOut:
    """Retrieves driver object based specific Id 

    Raises:
        HTTPException 404(not found): if  Driver not found in the db
        HTTPException 400(bad request): if  Invalid driver ID format

    Returns:
        _type_: DriverOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    filter_dict = {"_id": ObjectId(id)}
    result = await get_driver(filter_dict)

    if not result:
        
        raise HTTPException(status_code=404, detail="Driver not found")

    return result


async def retrieve_drivers(start=0,stop=100) -> List[DriverOut]:
    """Retrieves DriverOut Objects in a list

    Returns:
        _type_: DriverOut
    """
    return await get_drivers(start=start,stop=stop)

async def authenticate_driver(user_data:DriverBase )->DriverOut:
    user = await get_driver(filter_dict={"email":user_data.email.lower()})

    if user != None:
        if check_password(password=user_data.password,hashed=user.password ):
          
            access_token = await add_access_tokens(token_data=accessTokenCreate(userId=user.id))
            token_activation = user.accountStatus==AccountStatus.ACTIVE
            token = create_jwt_token(access_token=access_token.accesstoken,user_id=user.id,user_type="DRIVER",is_activated=token_activation)
            refresh_token  = await add_refresh_tokens(token_data=refreshTokenCreate(userId=user.id,previousAccessToken=access_token.accesstoken))
            user.access_token= token
            user.refresh_token = refresh_token.refreshtoken
            return user
        else:
            raise HTTPException(status_code=401, detail="Unathorized, Invalid Login credentials")
    else:
        raise HTTPException(status_code=404,detail="User not found")



async def refresh_driver_tokens_reduce_number_of_logins(user_refresh_data:DriverRefresh,expired_access_token):
    refreshObj= await get_refresh_tokens(user_refresh_data.refresh_token)
    if refreshObj:
        if not ObjectId.is_valid(refreshObj.userId):
            await delete_refresh_token(refreshToken=user_refresh_data.refresh_token)
            await delete_access_token(accessToken=expired_access_token)
            raise HTTPException(status_code=401,detail="Invalid refresh token")
        if refreshObj.previousAccessToken==expired_access_token:
            user = await get_driver(filter_dict={"_id":ObjectId(refreshObj.userId)})
            
            if user!= None:
                    access_token = await add_access_tokens(token_data=accessTokenCreate(userId=user.id))
                    token_activation = user.accountStatus==AccountStatus.ACTIVE
                    token = create_jwt_token(access_token=access_token.accesstoken,user_id=user.id,user_type="DRIVER",is_activated=token_activation)
                    refresh_token  = await add_refresh_tokens(token_data=refreshTokenCreate(userId=user.id,previousAccessToken=access_token.accesstoken))
                    user.access_token= token
                    user.refresh_token = refresh_token.refreshtoken
                    await delete_access_token(accessToken=expired_access_token)
                    await delete_refresh_token(refreshToken=user_refresh_data.refresh_token)
                    return user
     
        await delete_refresh_token(refreshToken=user_refresh_data.refresh_token)
        await delete_access_token(accessToken=expired_access_token)
  
    raise HTTPException(status_code=404,detail="Invalid refresh token ")  

async def update_driver_by_id(driver_id: str, driver_data: Union[DriverUpdate,DriverUpdateProfile],is_password_getting_changed:bool=False) -> DriverOut:
    """updates an entry of driver in the database

    Raises:
        HTTPException 404(not found): if Driver not found or update failed
        HTTPException 400(not found): Invalid driver ID format

    Returns:
        _type_: DriverOut
    """
    from celery_worker import celery_app
    if not ObjectId.is_valid(driver_id):
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    filter_dict = {"_id": ObjectId(driver_id)}
    result = await update_driver(filter_dict, driver_data)
    
    if not result:
        raise HTTPException(status_code=404, detail="Driver not found or update failed")
    if is_password_getting_changed==True:
        result = celery_app.send_task("celery_worker.run_async_task",args=["delete_tokens",{"userId": driver_id} ])
    return result

async def driver_reset_password_intiation(driver_details:ResetPasswordInitiation)->ResetPasswordInitiationResponse:
 
    driver = await get_driver(filter_dict={"email":driver_details.email})
    if driver:
         
        OTP=generate_otp()
        success = send_otp(otp=OTP,user_email=driver_details.email)
        if success==0:
            token  = ResetTokenBase(userId=driver.id,userType=UserType.driver,otp=OTP)
            reset_token_create  =ResetTokenCreate(**token.model_dump())
            reset_token =  await create_reset_token(reset_token_data=reset_token_create)
            response = ResetPasswordInitiationResponse(resetToken=reset_token.id)
            return response
        else: raise HTTPException(status_code=500, detail="OTP DIDN't send to the user email")
    else: raise HTTPException(status_code=404, detail="No driver has this email on the platform")
 
async def driver_reset_password_conclusion(
    driver_details: ResetPasswordConclusion
) -> bool:

    # 1️⃣ Validate reset token ID
    try:
        reset_token_id = ObjectId(driver_details.resetToken)
    except InvalidId:
        raise ValueError("Invalid reset token")

    # 2️⃣ Fetch reset token
    token = await get_reset_token(filter_dict={"_id": reset_token_id})

    if not token:
        raise HTTPException(status_code=404,detail="Reset token not found or expired")

    # 3️⃣ Validate token user type
    if token.userType != UserType.driver:
        raise HTTPException(status_code=403,detail="Reset token is not for a driver")

    # 4️⃣ Validate OTP
    if token.otp != driver_details.otp:
        raise HTTPException(status_code=400,detail="Invalid OTP")

    # 5️⃣ Update driver password
    driver_update = DriverUpdatePassword(
        password=driver_details.password
    )

    result = await update_driver_by_id(
        driver_id=token.userId,
        driver_data=driver_update,
        is_password_getting_changed=True
    )

    if not result:
        raise HTTPException(status_code=500,detail="Failed to update driver password")

    return True

async def update_driver_by_id_admin_func(
    driver_id: str,
    driver_data: DriverUpdateAccountStatus,
) -> DriverOut:
    """
    Update driver entry with state validation and no-op prevention.
    """

    # 1️⃣ Validate ID
    if not ObjectId.is_valid(driver_id):
        raise HTTPException(status_code=400, detail="Invalid driver ID format")

    filter_dict = {"_id": ObjectId(driver_id)}

    if driver_data.accountStatus is None:
        raise HTTPException(status_code=400, detail="Account status is required")

    # 2️⃣ Fetch existing driver
    existing_driver = await get_driver(filter_dict)
    if not existing_driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # 3️⃣ Prevent unnecessary rewrite (no-op)
    if (
        driver_data.accountStatus is not None
        and driver_data.accountStatus == existing_driver.accountStatus
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Driver is already in '{existing_driver.accountStatus}' state",
        )

    # 4️⃣ Enforce state transition rules
    if driver_data.accountStatus is not None:
        current_status = existing_driver.accountStatus
        new_status = driver_data.accountStatus

        if new_status == AccountStatus.ACTIVE:
            bg = await fetch_background_check(driver_id)
            if not bg or bg.status != "passed":
                raise HTTPException(
                    status_code=400,
                    detail="Background check must be PASSED before activation",
                )

        allowed_next_states = ALLOWED_ACCOUNT_STATUS_TRANSITIONS.get(
            current_status, set()
        )

        if new_status not in allowed_next_states:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition: {current_status} → {new_status}",
            )

    # 5️⃣ Perform update
    result = await update_driver(filter_dict, driver_data)

    if not result:
        raise HTTPException(
            status_code=404, detail="Driver not found or update failed"
        )

    return result

async def update_driver_by_stripe_account_id(stripe_account_id: str, driver_data: DriverUpdate) -> DriverOut:
    """updates a driver by Stripe account ID in the database

    Raises:
        HTTPException 404(not found): if Driver not found or update failed
        HTTPException 400(not found): Invalid Stripe account ID format

    Returns:
        _type_: DriverOut
    """
    if not stripe_account_id:
        raise HTTPException(status_code=400, detail="Invalid Stripe account ID format")

    filter_dict = {"stripeAccountId": stripe_account_id}
    result = await update_driver(filter_dict, driver_data)

    if not result:
        raise HTTPException(status_code=404, detail="Driver not found or update failed")
    return result


async def update_driver_location(driver_id: str, location: DriverLocationUpdate) -> None:
    if not ObjectId.is_valid(driver_id):
        raise HTTPException(status_code=400, detail="Invalid driver ID format")
    driver = await retrieve_driver_by_driver_id(id=driver_id)
    if not getattr(driver, "profileComplete", False):
        raise HTTPException(status_code=400, detail="Vehicle details must be set before updating location")
    vehicle_type = getattr(driver, "vehicleType", None)
    await update_driver_presence(
        driver_id=driver_id,
        latitude=location.latitude,
        longitude=location.longitude,
        vehicle_type=str(vehicle_type) if vehicle_type else None,
        profile_complete=getattr(driver, "profileComplete", False),
        timestamp=location.timestamp,
        account_status=getattr(driver, "accountStatus", None),
    )


async def update_driver_vehicle(driver_id: str, vehicle_details: DriverVehicleUpdate) -> DriverOut:
    if not ObjectId.is_valid(driver_id):
        raise HTTPException(status_code=400, detail="Invalid driver ID format")
    filter_dict = {"_id": ObjectId(driver_id)}
    result = await update_driver(filter_dict, vehicle_details)
    if not result:
        raise HTTPException(status_code=404, detail="Driver not found or update failed")
    return result



# -------------------------------------
# ------------ COMBINED LOGIC ---------
# -------------------------------------

async def ban_drivers(user_id: str, user:dict) -> dict:
    user_data= DriverUpdateAccountStatus(**user)
    update =await update_driver_by_id_admin_func(driver_id=user_id,driver_data=user_data)
    rider = await retrieve_driver_by_driver_id(id=user_id)
    send_ban_warning(rider.email,rider.firstName,rider.lastName)
    
    
    
    
# -----------------------------------------
# ------------ NOTIFICATION LOGIC ---------
# -----------------------------------------
    
async def notify_all_drivers_new_ride(
    ride_id: str,
    pickup: str,
    destination: str,
    fare: int,
    vehicle_type: str = "UNKNOWN",
    rider_id: str | None = None,
):
    await publish_ride_request(
        ride_id=ride_id,
        pickup=pickup,
        destination=destination,
        vehicle_type=vehicle_type,
        fare_estimate=fare,
        rider_id=rider_id,
    )
    
    

async def notify_driver_new_ride(
    driver_id: str,
    ride_id: str,
    pickup: str,
    destination: str,
    fare: int,
    vehicle_type: str = "UNKNOWN",
    rider_id: str | None = None,
):
    await publish_ride_request_to_driver(
        driver_id=driver_id,
        ride_id=ride_id,
        pickup=pickup,
        destination=destination,
        vehicle_type=vehicle_type,
        fare_estimate=fare,
        rider_id=rider_id,
    )
