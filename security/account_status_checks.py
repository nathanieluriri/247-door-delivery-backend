

from fastapi import Depends, HTTPException, Request,status
from schemas.imports import AccountStatus
from schemas.tokens_schema import accessTokenOut
from security.auth import verify_admin_token, verify_token_driver_role, verify_token_rider_role
from services.admin_service import retrieve_admin_by_admin_id
from services.rider_service import retrieve_rider_by_rider_id
from services.driver_service import retrieve_driver_by_driver_id


def _extract_user_id(token) -> str | None:
    if token is None:
        return None
    if isinstance(token, dict):
        return token.get("userId") or token.get("user_id")
    return getattr(token, "userId", None) or getattr(token, "user_id", None)


async def check_admin_account_status_and_permissions(
    request: Request,
    token: dict = Depends(verify_admin_token),
):
    # 1️⃣ Load admin
    admin_id = _extract_user_id(token)
    if not admin_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )
    admin = await retrieve_admin_by_admin_id(id=admin_id)

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found",
        )

    # 2️⃣ Check account status
    if admin.accountStatus != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is not active",
        )

    # 3️⃣ Identify current route
    endpoint = request.scope.get("endpoint")
    if endpoint is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to resolve endpoint",
        )

    endpoint_name = endpoint.__name__
    request_method = request.method.upper()

    # 4️⃣ Ensure permissions exist
    permission_list = getattr(admin, "permissionList", None)

    if not permission_list or not permission_list.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No permissions assigned to admin",
        )

    # 5️⃣ Permission check
    for permission in permission_list.permissions:
        if (
            permission.name == endpoint_name
            and request_method in permission.methods
        ):
            # ✅ Authorized
            return admin

    # 6️⃣ Deny if no match
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Insufficient permissions",
    )
    
   # Rider account status check
async def check_rider_account_status(
    request: Request, 
    token: accessTokenOut = Depends(verify_token_rider_role)
):
    # Fetch the rider
    rider = await retrieve_rider_by_rider_id(id=token.userId)
    
    # Validate rider exists
    if not rider:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Rider not found",
        )
    
    # Check account status
    if getattr(rider, "accountStatus", None) != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rider account is not active",
        )
    
    return rider


# Driver account status check
async def check_driver_account_status(
    request: Request, 
    token: accessTokenOut = Depends(verify_token_driver_role)
):
    # Fetch the driver
    driver = await retrieve_driver_by_driver_id(id=token.userId)
    
    # Validate driver exists
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Driver not found",
        )
    
    # Check account status
    if getattr(driver, "accountStatus", None) != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Driver account is not active",
        )
    
    return driver
    
