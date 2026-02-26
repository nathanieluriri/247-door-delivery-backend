from core.database import db
import os

from schemas.tokens_schema import accessTokenCreate,refreshTokenCreate,accessTokenOut,refreshTokenOut
from pymongo import ReturnDocument
from datetime import datetime, timezone, timedelta
from dateutil import parser
from bson import ObjectId,errors
from fastapi import HTTPException
from repositories.admin_repo import get_admin
from security.encrypting_jwt import decode_jwt_token_without_expiration


def _refresh_token_expiry_days() -> int:
    raw_value = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS")
    try:
        days = int(raw_value) if raw_value is not None else 30
    except ValueError:
        days = 30
    return max(days, 1)


def _coerce_datetime(date_value) -> datetime | None:
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        if date_value.tzinfo is None:
            return date_value.replace(tzinfo=timezone.utc)
        return date_value.astimezone(timezone.utc)
    if isinstance(date_value, (int, float)):
        return datetime.fromtimestamp(date_value, tz=timezone.utc)
    try:
        parsed = parser.isoparse(str(date_value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resolve_refresh_token_expires_at(token: dict) -> datetime | None:
    explicit_expiration = _coerce_datetime(
        token.get("expiresAt") or token.get("expires_at")
    )
    if explicit_expiration is not None:
        return explicit_expiration
    created_at = _coerce_datetime(token.get("dateCreated"))
    if created_at is None:
        return None
    return created_at + timedelta(days=_refresh_token_expiry_days())

async def add_access_tokens(token_data:accessTokenCreate)->accessTokenOut:
    token = token_data.model_dump()
    token['role']="member"
    result = await db.accessToken.insert_one(token)
    tokn = await db.accessToken.find_one({"_id":result.inserted_id})
    accessToken = accessTokenOut(**tokn)
    
    return accessToken 
    

async def delete_access_and_refresh_token_with_user_id(userId:str)->bool:
     result = await db.refreshToken.delete_many({'userId':userId})
     result1 = await db.accessToken.delete_many({'userId':userId})
     return (result.acknowledged and result1.acknowledged)


async def add_admin_access_tokens(token_data:accessTokenCreate)->accessTokenOut:
    token = token_data.model_dump()
    token['role']="admin"
    token['status']="active"
    result = await db.accessToken.insert_one(token)
    tokn = await db.accessToken.find_one({"_id":result.inserted_id})
    accessToken = accessTokenOut(**tokn)
    
    return accessToken 

async def update_admin_access_tokens(token:str)->accessTokenOut:
    try:
        token_id = ObjectId(token)
    except errors.InvalidId:
        raise HTTPException(status_code=400,detail="Invalid access token id")
    updatedToken= await db.accessToken.find_one_and_update(
        filter={"_id":token_id},
        update={"$set": {'status':'active'}},
        return_document=ReturnDocument.AFTER
    )
    if not updatedToken:
        raise HTTPException(status_code=404,detail="Access token not found")
    return accessTokenOut(**updatedToken)
    
async def add_refresh_tokens(token_data:refreshTokenCreate)->refreshTokenOut:
    token = token_data.model_dump()
    if token.get("expiresAt") is None:
        token["expiresAt"] = datetime.now(timezone.utc) + timedelta(
            days=_refresh_token_expiry_days()
        )
    result = await db.refreshToken.insert_one(token)
    tokn = await db.refreshToken.find_one({"_id":result.inserted_id})
    refreshToken = refreshTokenOut(**tokn)
    return refreshToken

async def delete_access_token(accessToken:str)->bool:
    # await db.refreshToken.delete_many({"previousAccessToken":accessToken})
    try:
        obj_id = ObjectId(accessToken)
    except errors.InvalidId:
        return False
    result = await db.accessToken.find_one_and_delete({'_id':obj_id})
    return result is not None


async def delete_refresh_tokens_by_previous_access_token(accessToken: str) -> int:
    result = await db.refreshToken.delete_many({"previousAccessToken": accessToken})
    return result.deleted_count
    
    
async def delete_refresh_token(refreshToken:str)->bool:
    try:
        obj_id=ObjectId(refreshToken)
    except errors.InvalidId:
        raise HTTPException(status_code=401,detail="Invalid Refresh Id")
    result = await db.refreshToken.find_one_and_delete({"_id":obj_id})
    return result is not None



def is_older_than_days(date_value, days=10):
    """
    Accepts either an ISO-8601 string or a UNIX timestamp (int/float).
    Returns True if older than `days` days.
    """
    # Determine type and parse accordingly
    if isinstance(date_value, (int, float)):
        # It's a UNIX timestamp (seconds)
        created_date = datetime.fromtimestamp(date_value, tz=timezone.utc)
    else:
        # Assume ISO string
        created_date = parser.isoparse(str(date_value))

    # Get the current time in UTC (with same tzinfo)
    now = datetime.now(timezone.utc)

    # Check if the difference is greater than the given number of days
    return (now - created_date) > timedelta(days=days)


async def get_access_tokens(accessToken:str)->accessTokenOut | None:
    try:
        token_id = ObjectId(accessToken)
    except errors.InvalidId:
        return None
    token = await db.accessToken.find_one({"_id": token_id})
    if token:
        date_created = token.get("dateCreated")
        is_expired = (not date_created) or is_older_than_days(date_value=date_created)
        if is_expired:
            await delete_access_token(accessToken=str(token['_id']))
            return None
        if token.get("role",None)=="member":
            tokn = accessTokenOut(**token)
            return tokn
        elif token.get("role",None)=="admin":
            if token.get('status',None)=="active":
                tokn = accessTokenOut(**token)
                return tokn
            else:
                return None
        else:
            return None
    else:
        return None
    
    
    
async def get_admin_access_tokens(accessToken:str)->accessTokenOut | None:
    try:
        token_id = ObjectId(accessToken)
    except errors.InvalidId:
        return None
    token = await db.accessToken.find_one({"_id": token_id})
    if not token:
        return None
    date_created = token.get("dateCreated")
    if not date_created or is_older_than_days(date_value=date_created):
        await delete_access_token(accessToken=str(token['_id']))
        return None
    if token.get("role") != "admin":
        return None
    if token.get("status") not in (None, "active"):
        return None
    userId = token.get("userId")
    if not userId:
        return None
    if not await get_admin(filter_dict={"_id":ObjectId(userId)}):
        return None
    return accessTokenOut(**token)
   
    
        
from bson.errors import InvalidId

async def get_access_tokens_no_date_check(accessToken: str) -> accessTokenOut | None:
    try:
        # Try interpreting the token as an ObjectId
        object_id = ObjectId(accessToken)
        token = await db.accessToken.find_one({"_id": object_id})
    except (InvalidId, TypeError):
        # If it's not a valid ObjectId, fall back to decoding the token
        token = await decode_jwt_token_without_expiration(accessToken)
 
    if not token:
        print("No token found")
        return None

    role = token.get("role")
    status = token.get("status")

    if role == "member":
        return accessTokenOut(**token)
    elif role == "admin":
       return accessTokenOut(**token)
    else:
        return None

    
async def get_refresh_tokens(refreshToken:str)->refreshTokenOut | None:
    try:
        token_id = ObjectId(refreshToken)
    except errors.InvalidId:
        return None
    token = await db.refreshToken.find_one({"_id": token_id})
    if token:
        expires_at = _resolve_refresh_token_expires_at(token)
        if expires_at is None or datetime.now(timezone.utc) >= expires_at:
            await db.refreshToken.delete_one({"_id": token_id})
            return None
        if token.get("expiresAt") is None:
            await db.refreshToken.update_one(
                {"_id": token_id},
                {"$set": {"expiresAt": expires_at}},
            )
            token["expiresAt"] = expires_at
        tokn = refreshTokenOut(**token)
        return tokn

    else: return None
    
    
    
async def delete_all_tokens_with_user_id(userId:str):
    await db.refreshToken.delete_many(filter={"userId":userId})
    await db.accessToken.delete_many(filter={"userId":userId})
    
async def delete_all_tokens_with_admin_id(adminId:str):
    await db.refreshToken.delete_many(filter={"userId":adminId})
    await db.accessToken.delete_many(filter={"userId":adminId})
