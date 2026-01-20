from schemas.tokens_schema import refreshTokenOut,accessTokenOut,refreshTokenCreate,accessTokenCreate
from security.encrypting_jwt import create_jwt_admin_token,create_jwt_member_token,decode_jwt_token,decode_jwt_token_without_expiration
from bson import errors,ObjectId
from fastapi import HTTPException,status




async def generate_member_access_tokens(userId)->accessTokenOut:
    from repositories.tokens_repo import add_access_tokens

    try:
        ObjectId(userId)
    except errors.InvalidId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid User Id")

    new_access_token = await add_access_tokens(token_data=accessTokenCreate(userId=userId))
    new_access_token.accesstoken = await create_jwt_member_token(token=new_access_token.accesstoken)
    
    return new_access_token



async def generate_admin_access_tokens(userId)->accessTokenOut:
    from repositories.tokens_repo import add_admin_access_tokens

    try:
        ObjectId(userId)
    except errors.InvalidId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid User Id")    # or raise an error / log it    

    new_access_token = await add_admin_access_tokens(token_data=accessTokenCreate(userId=userId))
    new_access_token.accesstoken = await create_jwt_admin_token(token=new_access_token.accesstoken,userId=userId)
    return new_access_token
    
    
    
async def generate_refresh_tokens(userId,accessToken)->refreshTokenOut:
    from repositories.tokens_repo import add_refresh_tokens

    try:
        ObjectId(userId)
    except errors.InvalidId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid User Id While trying to create refresh token")    # or raise an error / log it    

    decoded_access_token = await decode_jwt_token(accessToken)
    token_id = None
    if isinstance(decoded_access_token, dict):
        token_id = decoded_access_token.get("accessToken") or decoded_access_token.get("access_token")
    if not token_id:
        token_id = accessToken
    try:
        ObjectId(token_id)
    except errors.InvalidId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Access Id While trying to create refresh token")    # or raise an error / log it    

    new_refresh_token = await add_refresh_tokens(
        token_data=refreshTokenCreate(userId=userId,previousAccessToken=token_id)
    )
    return new_refresh_token


async def validate_refreshToken(refreshToken:str):
    from repositories.tokens_repo import get_refresh_tokens

    try:
        obj_id = ObjectId(refreshToken)
    except errors.InvalidId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Refresh Id")   # or raise an error / log it    

    refresh_token = await get_refresh_tokens(refreshToken=refreshToken)
    if refresh_token:
        new_refresh_token = await generate_refresh_tokens(userId=refresh_token.userId,accessToken=refresh_token.previousAccessToken)
        return new_refresh_token
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Couldn't Find Refresh Id")
    


async def validate_member_accesstoken(accessToken:str):
    from repositories.tokens_repo import get_access_tokens

    decodedAccessToken = await decode_jwt_token(token=accessToken)
    if not decodedAccessToken:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Access Token")
    token_id = decodedAccessToken.get("accessToken") or decodedAccessToken.get("access_token")
    if not token_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Access Token")
    try:
        ObjectId(token_id)
    except errors.InvalidId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Access Token")   # or raise an error / log it    

    validatedAccessToken= await get_access_tokens(accessToken=token_id)
    if validatedAccessToken:
        return validatedAccessToken
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Couldn't Find Access Tokens While Validating Member Access Tokens")
    
    
async def validate_admin_accesstoken_otp(accessToken:str):
    from core.database import db

    decodedAccessToken = await decode_jwt_token(token=accessToken)
    if not decodedAccessToken:
        return None
    token_id = decodedAccessToken.get("accessToken") or decodedAccessToken.get("access_token")
    if not token_id:
        return None
    try:
        obj_id = ObjectId(token_id)
    except errors.InvalidId:
        return None  # or raise an error / log it    

    if decodedAccessToken.get("role") != "admin":
        return None

    token_doc = await db.accessToken.find_one({"_id": obj_id})
    if not token_doc:
        return None
    if token_doc.get("role") != "admin":
        return None
    if token_doc.get("status") == "active":
        return "active"
    return accessTokenOut(**token_doc)
    
async def validate_admin_accesstoken(accessToken:str):
     
    from repositories.tokens_repo import get_admin_access_tokens
    decodedAccessToken = await decode_jwt_token(token=accessToken)
    if not decodedAccessToken:
        return None
    token_id = decodedAccessToken.get("accessToken") or decodedAccessToken.get("access_token")
    if not token_id:
        return None
    try:
        obj_id = ObjectId(token_id)
    except errors.InvalidId:
        return None  # or raise an error / log it    

    if decodedAccessToken.get("role") != "admin":
        return None

    validatedAccessToken= await get_admin_access_tokens(accessToken=token_id)
    if isinstance(validatedAccessToken, accessTokenOut):
        return validatedAccessToken
    return None
    
    
async def validate_expired_admin_accesstoken(accessToken:str):
    from repositories.tokens_repo import get_admin_access_tokens

    decodedAccessToken = await decode_jwt_token_without_expiration(token=accessToken)
    if not decodedAccessToken:
        return None
    token_id = decodedAccessToken.get("accessToken") or decodedAccessToken.get("access_token")
    if not token_id:
        return None
    try:
        ObjectId(token_id)
    except errors.InvalidId:
        return None  # or raise an error / log it    

    
    if decodedAccessToken:
        if decodedAccessToken.get('role')=="admin":
            validatedAccessToken= await get_admin_access_tokens(accessToken=token_id)
            if validatedAccessToken:
                return validatedAccessToken
            return None
        else:
            return None  
        
    else:
        return None 
    
    
    
    
    
    
    
    
async def validate_member_accesstoken_without_expiration(accessToken:str):
    from repositories.tokens_repo import get_access_tokens_no_date_check
    decodedAccessToken = await decode_jwt_token_without_expiration(token=accessToken)
    if not decodedAccessToken:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Couldn't Find Refresh Id")
    token_id = decodedAccessToken.get("accessToken") or decodedAccessToken.get("access_token")
    if not token_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Access Id")
    try:
        ObjectId(token_id)
    except errors.InvalidId:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Access Id")   # or raise an error / log it    

    validatedAccessToken= await get_access_tokens_no_date_check(accessToken=token_id)
    if validatedAccessToken:
        return validatedAccessToken
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail="Couldn't Find Refresh Id")
    
