# auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from security.tokens import validate_admin_accesstoken,validate_admin_accesstoken_otp,generate_refresh_tokens,generate_member_access_tokens, validate_member_accesstoken, validate_refreshToken,validate_member_accesstoken_without_expiration,generate_admin_access_tokens,validate_expired_admin_accesstoken
from security.encrypting_jwt import JWTPayload, decode_jwt_token,decode_jwt_token_without_expiration
from repositories.tokens_repo import get_access_tokens,get_access_tokens_no_date_check
from schemas.tokens_schema import refreshedToken,accessTokenOut
from services.driver_service import retrieve_driver_by_driver_id
from services.rider_service import retrieve_rider_by_rider_id


token_auth_scheme = HTTPBearer()
async def verify_token(token: str = Depends(token_auth_scheme))->JWTPayload:
    decoded_token = await decode_jwt_token(token=token.credentials) # type: ignore
    if not decoded_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    if decoded_token.get("user_type")=="RIDER":
        rider = await retrieve_rider_by_rider_id(id=decoded_token.get("user_id"))
        if rider:
            return JWTPayload(**decoded_token)
    elif decoded_token.get("user_type")=="DRIVER":
        driver = await retrieve_driver_by_driver_id(id=decoded_token.get("user_id"))
        if driver:
            return JWTPayload(**decoded_token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token"
    )
async def verify_token_to_refresh(token: str = Depends(token_auth_scheme))->accessTokenOut:
    tokens = await decode_jwt_token_without_expiration(token=token.credentials) # type: ignore
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    access_token = tokens.get("access_token") or tokens.get("accessToken")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    result = await get_access_tokens_no_date_check(accessToken=access_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return result
    
    

async def verify_token_rider_role(token: str = Depends(token_auth_scheme))->accessTokenOut:
    decoded_token = await decode_jwt_token(token=token.credentials) # type: ignore
    if not decoded_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    access_token = decoded_token.get("access_token") or decoded_token.get("accessToken")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    result = await get_access_tokens(accessToken=access_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    user = await retrieve_rider_by_rider_id(id=result.userId)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return result
 
            
async def verify_token_driver_role(token: str = Depends(token_auth_scheme))->accessTokenOut:
    decoded_token = await decode_jwt_token(token=token.credentials) # type: ignore
    if not decoded_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    access_token = decoded_token.get("access_token") or decoded_token.get("accessToken")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    result = await get_access_tokens(accessToken=access_token)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    driver = await retrieve_driver_by_driver_id(id=result.userId)
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    return result
async def verify_admin_token(token: str = Depends(token_auth_scheme))->dict:
    from repositories.tokens_repo import get_admin_access_tokens
    try:
        decoded_access_token = await decode_jwt_token(token=token.credentials) # type: ignore
        if not decoded_access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin token"
            )
        access_token = decoded_access_token.get("accessToken") or decoded_access_token.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin token"
            )
        result = await get_admin_access_tokens(accessToken=access_token)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin token"
            )
        if isinstance(result, accessTokenOut):
            return decoded_access_token
        # If result is not accessTokenOut, raise exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    except TypeError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access Token Expired")
    
    
           
async def verify_admin_token_otp(token: str = Depends(token_auth_scheme))->dict:
    try:
        result = await validate_admin_accesstoken_otp(accessToken=str(token.credentials)) # type: ignore

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin token"
            )
        if result == "active":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin Token has been activated"
            )
        if isinstance(result, accessTokenOut):
            decoded_access_token = await decode_jwt_token(token=token.credentials) # type: ignore
            if not decoded_access_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid admin token"
                )
            return decoded_access_token
        # If result is not accessTokenOut and not handled above, raise exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token"
        )
    except TypeError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access Token Expired")


async def verify_any_token(token:str=Depends(token_auth_scheme))->dict | JWTPayload:
    token_type = await decode_jwt_token(token=token.credentials) # type: ignore
    if isinstance(token_type,dict):
        if token_type.get('role')=='admin':
            return await verify_admin_token(token=token)
        elif token_type.get("role")=='member':
            return await verify_token(token=token)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token Type"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token"
        )
