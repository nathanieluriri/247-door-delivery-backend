
from bson import ObjectId
from fastapi import HTTPException
from typing import List

from repositories.rider_repo import (
    create_rider,
    get_rider,
    get_riders,
    update_rider,
    delete_rider,
)
from schemas.imports import ALLOWED_ACCOUNT_STATUS_TRANSITIONS
from schemas.rider_schema import RiderCreate, RiderUpdate, RiderOut,RiderBase,RiderRefresh
from security.hash import check_password
from security.encrypting_jwt import create_jwt_member_token
from repositories.tokens_repo import add_refresh_tokens, add_access_tokens, accessTokenCreate,accessTokenOut,refreshTokenCreate
from repositories.tokens_repo import get_refresh_tokens,get_access_tokens,delete_access_token,delete_refresh_token,delete_all_tokens_with_user_id
from authlib.integrations.starlette_client import OAuth
import os
from dotenv import load_dotenv

from services.email_service import send_ban_warning


load_dotenv()

 
oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

# -----------------------------------
# USER MANAGEMENT LOGIC
# -----------------------------------
async def add_rider(user_data: RiderCreate) -> RiderOut:
    """adds an entry of RiderCreate to the database and returns an object

    Returns:
        _type_: RiderOut
    """
    user =  await get_rider(filter_dict={"email":user_data.email})
    if user==None:
        new_rider= await create_rider(user_data)
        access_token = await add_access_tokens(token_data=accessTokenCreate(userId=new_rider.id))
        refresh_token  = await add_refresh_tokens(token_data=refreshTokenCreate(userId=new_rider.id,previousAccessToken=access_token.accesstoken))
        new_rider.password=""
        new_rider.access_token= access_token.accesstoken 
        new_rider.refresh_token = refresh_token.refreshtoken
        return new_rider
    else:
        raise HTTPException(status_code=409,detail="Rider Already exists")

async def authenticate_rider(user_data:RiderBase )->RiderOut:
    user = await get_rider(filter_dict={"email":user_data.email})

    if user != None:
        if check_password(password=user_data.password,hashed=user.password ):
            user.password=""
            access_token = await add_access_tokens(token_data=accessTokenCreate(userId=user.id))
            refresh_token  = await add_refresh_tokens(token_data=refreshTokenCreate(userId=user.id,previousAccessToken=access_token.accesstoken))
            user.access_token= access_token.accesstoken 
            user.refresh_token = refresh_token.refreshtoken
            return user
        else:
            raise HTTPException(status_code=401, detail="Unathorized, Invalid Login credentials")
    else:
        raise HTTPException(status_code=404,detail="Rider not found")

async def refresh_rider_tokens_reduce_number_of_logins(user_refresh_data:RiderRefresh,expired_access_token):
    refreshObj= await get_refresh_tokens(user_refresh_data.refresh_token)
    if refreshObj:
        if refreshObj.previousAccessToken==expired_access_token:
            user = await get_rider(filter_dict={"_id":ObjectId(refreshObj.userId)})
            
            if user!= None:
                    access_token = await add_access_tokens(token_data=accessTokenCreate(userId=user.id))
                    refresh_token  = await add_refresh_tokens(token_data=refreshTokenCreate(userId=user.id,previousAccessToken=access_token.accesstoken))
                    user.access_token= access_token.accesstoken 
                    user.refresh_token = refresh_token.refreshtoken
                    await delete_access_token(accessToken=expired_access_token)
                    await delete_refresh_token(refreshToken=user_refresh_data.refresh_token)
                    return user
     
        await delete_refresh_token(refreshToken=user_refresh_data.refresh_token)
        await delete_access_token(accessToken=expired_access_token)
  
    raise HTTPException(status_code=404,detail="Invalid refresh token ")  
        
async def remove_rider(user_id: str):
    """deletes a field from the database and removes RiderCreateobject 

    Raises:
        HTTPException 400: Invalid user ID format
        HTTPException 404:  Rider not found
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    filter_dict = {"_id": ObjectId(user_id)}
    result = await delete_rider(filter_dict)
    await delete_all_tokens_with_user_id(userId=user_id)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rider not found")


async def retrieve_rider_by_rider_id(id: str) -> RiderOut:
    """Retrieves user object based specific Id 

    Raises:
        HTTPException 404(not found): if  Rider not found in the db
        HTTPException 400(bad request): if  Invalid user ID format

    Returns:
        _type_: RiderOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    filter_dict = {"_id": ObjectId(id)}
    result = await get_rider(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Rider not found")

    return result


async def retrieve_riders(start=0,stop=100) -> List[RiderOut]:
    """Retrieves RiderOut Objects in a list

    Returns:
        _type_: RiderOut
    """
    return await get_riders(start=start,stop=stop)


async def update_rider_by_id(user_id: str, user_data: RiderUpdate) -> RiderOut:
    """_summary_

    Raises:
        HTTPException 404(not found): if Rider not found or update failed
        HTTPException 400(not found): Invalid user ID format

    Returns:
        _type_: RiderOut
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    filter_dict = {"_id": ObjectId(user_id)}
    result = await update_rider(filter_dict, user_data)

    if not result:
        raise HTTPException(status_code=404, detail="Rider not found or update failed")

    return result

async def update_rider_by_id_admin_func(
    user_id: str,
    user_data: RiderUpdate,
) -> RiderOut:
    """
    Update rider entry with state validation and no-op prevention.
    """

    # 1️⃣ Validate ID
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid rider ID format")

    filter_dict = {"_id": ObjectId(user_id)}

    # 2️⃣ Fetch existing rider
    existing_rider = await get_rider(filter_dict)
    if not existing_rider:
        raise HTTPException(status_code=404, detail="Rider not found")

    # 3️⃣ Prevent unnecessary rewrite (no-op)
    # Checks if we are trying to update the status to what it currently is
    if (
        user_data.accountStatus is not None
        and user_data.accountStatus == existing_rider.accountStatus
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Rider is already in '{existing_rider.accountStatus}' state",
        )

    # 4️⃣ Enforce state transition rules
    if user_data.accountStatus is not None:
        current_status = existing_rider.accountStatus
        new_status = user_data.accountStatus

        allowed_next_states = ALLOWED_ACCOUNT_STATUS_TRANSITIONS.get(
            current_status, set()
        )

        if new_status not in allowed_next_states:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition: {current_status} → {new_status}",
            )

    # 5️⃣ Perform update
    result = await update_rider(filter_dict, user_data)

    if not result:
        raise HTTPException(
            status_code=404, detail="Rider not found or update failed"
        )

    return result

# -----------------------------------
# COMBINED LOGIC
# -----------------------------------

async def ban_riders(user_id: str, user:dict) -> dict:
    user_data= RiderUpdate(**user)
    update =await update_rider_by_id_admin_func(user_id=user_id,user_data=user_data)
    rider = await retrieve_rider_by_rider_id(id=user_id)
    send_ban_warning(rider.firstName,rider.lastName)
    
    
    
