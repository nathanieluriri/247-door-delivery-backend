
import os
from urllib.parse import urlencode
from fastapi import APIRouter, Body, HTTPException, Query, Request, status, Path, Depends, UploadFile, File, Form
from typing import List, Optional
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from schemas.imports import PayoutOptions, ResetPasswordConclusion, ResetPasswordInitiation, ResetPasswordInitiationResponse, RideStatus
from schemas.rating import RatingBase, RatingCreate
from schemas.response_schema import APIResponse
from core.staff_payment import get_staff_payment_service
from schemas.tokens_schema import accessTokenOut
from schemas.storage_upload import CloudflareUploadResponse
from schemas.payout import (
    PayoutCreate,
    PayoutOut,
    PayoutBase,
    PayoutUpdate,
    PayoutBalanceOut,
    PayoutRequestIn,
)
from repositories.tokens_repo import delete_access_token, delete_refresh_tokens_by_previous_access_token, get_access_tokens
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
    DriverLocationUpdate,
    DriverUpdateProfile,
    DriverVehicleUpdate,
)
from schemas.ride import RideUpdate
from schemas.driver_document import DriverDocumentCreate, DriverDocumentOut, DocumentType, DocumentStatus
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
    update_driver_location,
    update_driver_vehicle,
    refresh_driver_tokens_reduce_number_of_logins,
    oauth

)
from services.driver_document_service import (
    store_driver_document,
    get_driver_documents,
    retrieve_driver_document,
    get_latest_document_for_driver,
    list_latest_documents_for_driver,
)
from core.storage import store_file, get_signed_url, verify_integrity, quarantine_file
from services.quarantine_service import log_quarantine_event
from core.antivirus import scan_bytes
from security.auth import verify_token_to_refresh, verify_token_driver_role
from security.encrypting_jwt import decode_jwt_token
from services.rating_service import add_rating, retrieve_rating_by_user_id
from services.ride_service import retrieve_rides_by_driver_id, retrieve_ride_by_ride_id, update_ride_by_id


router = APIRouter(prefix="/drivers", tags=["Drivers"])
SUCCESS_PAGE_URL = os.getenv("SUCCESS_PAGE_URL", "http://localhost:8080/success")
ERROR_PAGE_URL   = os.getenv("ERROR_PAGE_URL",   "http://localhost:8080/error")
MAX_CLOUDFLARE_UPLOAD_BYTES = 10 * 1024 * 1024
optional_bearer_auth = HTTPBearer(auto_error=False)


async def _get_optional_driver_token(
    creds: Optional[HTTPAuthorizationCredentials],
) -> Optional[accessTokenOut]:
    if not creds:
        return None
    decoded_token = await decode_jwt_token(token=creds.credentials)  # type: ignore[arg-type]
    if not decoded_token:
        return None
    access_token = decoded_token.get("access_token") or decoded_token.get("accessToken")
    if not access_token:
        return None
    result = await get_access_tokens(accessToken=access_token)
    if result is None:
        return None
    driver = await retrieve_driver_by_driver_id(id=result.userId)
    if not driver:
        return None
    return result
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
            driver = await add_driver(driver_data=new_data)
        except:
            driver = await authenticate_driver(user_data=old_data)
        # user_info.get("email_verified",False)
        # user_info.get("given_name",None)
        # user_info.get("family_name",None)
        # user_info.get("picture",None)
        access_token = driver.access_token
        refresh_token = driver.refresh_token
        query = urlencode(
            {
                "status": "success",
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        )
        success_url = f"{SUCCESS_PAGE_URL}?{query}"
        return RedirectResponse(url=success_url, status_code=status.HTTP_302_FOUND)
    else:
        raise HTTPException(status_code=400,detail={"status": "failed", "message": "No user info found"})



@router.get("/" ,response_model_exclude={"data": {"__all__": {"password"}}}, response_model=APIResponse[List[DriverOut]],response_model_exclude_none=True,dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def list_drivers(start:int= 0, stop:int=100):
    items = await retrieve_drivers(start=start,stop=stop)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.get("/me", response_model_exclude={"data": {"password"}},response_model=APIResponse[DriverOut],dependencies=[Depends(verify_token_driver_role)],response_model_exclude_none=True)
async def get_driver_details(token:accessTokenOut = Depends(verify_token_driver_role)):
 
    try:
        items = await retrieve_driver_by_driver_id(id=token.userId)
        return APIResponse(status_code=200, data=items, detail="users items fetched")
    except Exception as e:
        if str(e) == "'JWTPayload' object has no attribute 'userId'":
            raise HTTPException(status_code=401,detail=f"Invalid Token Use Driver Id if you want to access driver details with these tokens")
        raise HTTPException(status_code=500,detail=f"{e}")
     
@router.post("/signup", response_model_exclude={"data": {"password"}},response_model=APIResponse[DriverOut])
async def signup_new_driver(user_data:DriverCreate):
    if len(user_data.password)<8:
        raise HTTPException(status_code=401,detail="Password too short")
    items = await add_driver(driver_data=user_data)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.post("/login",response_model_exclude={"data": {"password"}}, response_model=APIResponse[DriverOut])
async def login_driver(user_data:DriverBase):
    if len(user_data.password)<8:
        raise HTTPException(status_code=401,detail="Password too short")
    items = await authenticate_driver(user_data=user_data)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")



@router.post("/refresh",response_model_exclude={"data": {"password"}},response_model=APIResponse[DriverOut],dependencies=[Depends(verify_token_to_refresh)])
async def refresh_driver_tokens(user_data:DriverRefresh,token:accessTokenOut = Depends(verify_token_to_refresh)):
    
    items= await refresh_driver_tokens_reduce_number_of_logins(user_refresh_data=user_data,expired_access_token=token.accesstoken)

    return APIResponse(status_code=200, data=items, detail="users items fetched")


@router.patch("/profile",dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def update_driver_profile(driver_details:DriverUpdateProfile,token:accessTokenOut = Depends(verify_token_driver_role)):
    driver =  await update_driver_by_id(driver_id=token.userId,driver_data=driver_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")
     


@router.post("/location", response_model=APIResponse[bool], dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def update_driver_current_location(
    payload: DriverLocationUpdate,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    await update_driver_location(driver_id=token.userId, location=payload)
    return APIResponse(status_code=200, data=True, detail="Location updated")


@router.put("/vehicle", response_model=APIResponse[DriverOut], dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def update_driver_vehicle_details(
    payload: DriverVehicleUpdate,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    driver = await update_driver_vehicle(driver_id=token.userId, vehicle_details=payload)
    return APIResponse(status_code=200, data=driver, detail="Vehicle details updated")


@router.get("/vehicle", response_model=APIResponse[dict], response_model_exclude_none=True)
async def get_driver_vehicle_info(
    driver_id: Optional[str] = Query(default=None),
    token: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_auth),
):
    resolved_driver_id = driver_id
    if not resolved_driver_id:
        token_data = await _get_optional_driver_token(token)
        if token_data:
            resolved_driver_id = token_data.userId

    if not resolved_driver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="driver_id is required when not authenticated as a driver",
        )

    driver = await retrieve_driver_by_driver_id(id=resolved_driver_id)
    if not driver:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found",
        )

    vehicle_info = {
        "driverId": driver.id,
        "vehicleType": driver.vehicleType,
        "vehicleMake": driver.vehicleMake,
        "vehicleModel": driver.vehicleModel,
        "vehicleColor": driver.vehicleColor,
        "vehiclePlateNumber": driver.vehiclePlateNumber,
        "vehicleYear": driver.vehicleYear,
    }

    return APIResponse(status_code=200, data=vehicle_info, detail="Vehicle info retrieved")


# ---------------------------------
# ------- DOCUMENT UPLOAD ---------
# ---------------------------------


@router.post(
    "/documents/upload",
    response_model=APIResponse[DriverDocumentOut],
    dependencies=[Depends(verify_token_driver_role)],
)
async def upload_driver_document(
    documentType: DocumentType = Form(...),
    file: UploadFile = File(...),
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Upload a driver compliance document. Storage backend is configurable
    (local or S3) and metadata is persisted in Mongo.
    """
    existing = await get_latest_document_for_driver(
        driver_id=token.userId,
        document_type=documentType,
        statuses=[DocumentStatus.PENDING, DocumentStatus.APPROVED],
    )
    if existing:
        if getattr(existing, "storageProvider", None) == "s3":
            existing.signedUrl = get_signed_url(existing.fileKey)
        return APIResponse(
            status_code=200,
            data=existing,
            detail="Document already uploaded; pending or approved documents must be reviewed before re-upload.",
        )

    content = await file.read()

    clean, reason = scan_bytes(content)
    if not clean:
        quarantined = quarantine_file(token.userId, file.filename, content, file.content_type)
        await log_quarantine_event(token.userId, quarantined.key, reason)
        raise HTTPException(status_code=400, detail=f"Infected file detected: {reason}")

    stored = store_file(
        driver_id=token.userId,
        filename=file.filename,
        content=content,
        content_type=file.content_type,
    )
    signed_url = stored.url or get_signed_url(stored.key)

    doc = DriverDocumentCreate(
        driverId=token.userId,
        documentType=documentType,
        fileKey=stored.key,
        fileName=file.filename,
        mimeType=file.content_type,
        storageProvider=stored.provider,
        signedUrl=signed_url,
        sha256=stored.sha256,
        md5=stored.md5,
    )
    created = await store_driver_document(doc)
    return APIResponse(status_code=200, data=created, detail="Document uploaded")


@router.post(
    "/uploads/cloudflare",
    response_model=APIResponse[CloudflareUploadResponse],
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
)
async def upload_driver_file_to_cloudflare(
    file: UploadFile = File(...),
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    if os.getenv("STORAGE_BACKEND", "local").lower() != "s3":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cloudflare upload requires STORAGE_BACKEND=s3",
        )

    content = await file.read()
    if len(content) > MAX_CLOUDFLARE_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Max size is 10MB.",
        )

    stored = store_file(
        driver_id=token.userId,
        filename=file.filename,
        content=content,
        content_type=file.content_type,
    )
    signed_url = stored.url or get_signed_url(stored.key)

    payload = CloudflareUploadResponse(
        key=stored.key,
        provider=stored.provider,
        signedUrl=signed_url,
        sha256=stored.sha256,
        md5=stored.md5,
        sizeBytes=len(content),
        contentType=file.content_type,
        filename=file.filename,
    )
    return APIResponse(status_code=200, data=payload, detail="File uploaded to Cloudflare")


@router.get(
    "/documents",
    response_model=APIResponse[List[DriverDocumentOut]],
    dependencies=[Depends(verify_token_driver_role)],
)
async def list_my_documents(token: accessTokenOut = Depends(verify_token_driver_role)):
    docs = await get_driver_documents(driver_id=token.userId)
    for d in docs:
        if getattr(d, "storageProvider", None) == "s3":
            d.signedUrl = get_signed_url(d.fileKey)
    return APIResponse(status_code=200, data=docs, detail="Documents fetched")


@router.get(
    "/documents/latest",
    response_model=APIResponse[List[DriverDocumentOut]],
    dependencies=[Depends(verify_token_driver_role)],
)
async def list_my_latest_documents_by_type(token: accessTokenOut = Depends(verify_token_driver_role)):
    docs = await list_latest_documents_for_driver(driver_id=token.userId)
    for d in docs:
        if getattr(d, "storageProvider", None) == "s3":
            d.signedUrl = get_signed_url(d.fileKey)
    return APIResponse(status_code=200, data=docs, detail="Latest documents fetched")


@router.get(
    "/documents/{docId}/verify",
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_token_driver_role)],
)
async def verify_document_integrity(docId: str, token: accessTokenOut = Depends(verify_token_driver_role)):
    doc = await retrieve_driver_document(docId)
    if not doc or doc.driverId != token.userId:
        raise HTTPException(status_code=404, detail="Document not found")
    ok = verify_integrity(doc.fileKey, doc.sha256)
    return APIResponse(status_code=200, data=ok, detail="Integrity verified" if ok else "Integrity check failed")



@router.delete("/account",dependencies=[Depends(verify_token_driver_role),Depends(check_driver_account_status)])
async def delete_user_account(token:accessTokenOut = Depends(verify_token_driver_role)):
    result = await remove_driver(driver_id=token.userId)
    return APIResponse(data=result,status_code=200,detail="Successfully deleted account")

@router.post("/logout", dependencies=[Depends(verify_token_driver_role)])
async def logout_driver(token: accessTokenOut = Depends(verify_token_driver_role)):
    if not token.accesstoken:
        raise HTTPException(status_code=400, detail="Invalid access token")
    await delete_refresh_tokens_by_previous_access_token(accessToken=token.accesstoken)
    deleted = await delete_access_token(accessToken=token.accesstoken)
    if not deleted:
        raise HTTPException(status_code=400, detail="Access token already invalidated")
    return APIResponse(status_code=200, data=True, detail="Logged out successfully")



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
    rating = await add_rating(rating_data=rider_rating,driverId=token.userId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Rated Rider")



# -------------------------------
# ------- RIDE MANAGEMENT ------- 
# -------------------------------




@router.post("/ride/{ride_id}/accept")
async def accept_ride(
    ride_id: str,
    token: accessTokenOut = Depends(verify_token_driver_role), 
):
    # Update ride to assign driver and change status to arrivingToPickup
    ride_update = RideUpdate(
        driverId=token.userId,
        rideStatus=RideStatus.arrivingToPickup
    )
    
    updated_ride = await update_ride_by_id(
        ride_id=ride_id,
        ride_data=ride_update,
        driver_id=token.userId
    )
    
    return APIResponse(
        status_code=200,
        data=updated_ride,
        detail="Ride accepted successfully"
    )
    
    
@router.post("/ride/{ride_id}")
async def retrieve_ride_details(
    ride_id: str,
    token: accessTokenOut = Depends(verify_token_driver_role), 
):
    ride = await retrieve_ride_by_ride_id(id=ride_id)
    
    if not ride:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ride not found"
        )
    
    return APIResponse(
        status_code=200,
        data=ride,
        detail="Ride details retrieved successfully"
    )


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

staff_payment_service = get_staff_payment_service()



# ------------------------------
# Driver Stripe Connect Onboarding
# ------------------------------
@router.post("/payout/onboard", response_model=APIResponse[dict])
async def onboard_driver_for_payments(token: accessTokenOut = Depends(verify_token_driver_role)):
    """
    Onboard driver for Stripe Connect payments.

    Creates a Stripe Connect Express account and generates onboarding link.
    Driver must complete onboarding before receiving payments.
    """
    # Get driver details
    driver = await retrieve_driver_by_driver_id(id=token.userId)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    try:
        onboarding_result = await staff_payment_service.onboard_driver(driver)
        return APIResponse(
            status_code=200,
            data=onboarding_result,
            detail="Driver onboarding initiated successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Onboarding failed: {str(e)}")

# ------------------------------
# Check Payment Eligibility Status
# ------------------------------
@router.get("/payout/status", response_model=APIResponse[dict])
async def get_driver_payment_status(token: accessTokenOut = Depends(verify_token_driver_role)):
    """
    Get driver's current payment status and eligibility.

    Returns information about Stripe Connect account status and payout eligibility.
    """
    # Get driver details
    driver = await retrieve_driver_by_driver_id(id=token.userId)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    try:
        status_result = await staff_payment_service.get_driver_payment_status(driver)
        return APIResponse(
            status_code=200,
            data=status_result,
            detail="Payment status retrieved successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Status check failed: {str(e)}")

# ------------------------------
# List Payouts (with pagination)
# ------------------------------

@router.get("/payouts", response_model=APIResponse[List[PayoutOut]])
async def list_previous_payouts(
    start: Optional[int] = Query(None, description="Start index for range-based pagination"),
    stop: Optional[int] = Query(None, description="Stop index for range-based pagination"),
    page_number: Optional[int] = Query(None, description="Page number for page-based pagination (0-indexed)"),
    token: accessTokenOut = Depends(verify_token_driver_role)
):
    """
    List all payout records for the authenticated driver.

    Supports multiple pagination methods:
    - Range-based: ?start=0&stop=10
    - Page-based: ?page_number=0 (uses PAGE_SIZE=10)
    - Default: First 100 records
    """
    PAGE_SIZE = 10

    # Case 1: Range-based pagination
    if start is not None and stop is not None:
        if start < 0 or stop <= start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'start' must be >= 0 and 'stop' must be > 'start'."
            )

        # Pass filters to the service layer
        items = await retrieve_payouts(driverId=token.userId, start=start, stop=stop)
        return APIResponse(status_code=200, data=items, detail=f"Fetched records {start} to {stop} successfully")

    # Case 2: Page-based pagination
    elif page_number is not None:
        if page_number < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'page_number' cannot be negative.")

        start_index = page_number * PAGE_SIZE
        stop_index = start_index + PAGE_SIZE
        # Pass filters to the service layer
        items = await retrieve_payouts(driverId=token.userId, start=start_index, stop=stop_index)
        return APIResponse(status_code=200, data=items, detail=f"Fetched page {page_number} successfully")

    # Case 3: Default (no params)
    else:
        # Pass filters to the service layer
        items = await retrieve_payouts(driverId=token.userId, start=0, stop=100)
        detail_msg = "Fetched first 100 records successfully"

        return APIResponse(status_code=200, data=items, detail=detail_msg)


# ------------------------------
# Retrieve a single Payout
# ------------------------------
@router.get("/payout/{id}", response_model=APIResponse[PayoutOut])
async def view_information_regarding_a_previous_payout(
    
    id: str = Path(..., description="payout ID to fetch specific item"),
    
    token:accessTokenOut = Depends(verify_token_driver_role)
    
):
    """
    Retrieves a single Payout by its ID.
    """
    item = await retrieve_payout_by_payout_id(id=id,driverId=token.userId)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payout not found")
    
    return APIResponse(status_code=200, data=item, detail="payout item fetched")



 



@router.get("/payout/balance", response_model=APIResponse[PayoutBalanceOut])
async def get_driver_available_balance(token: accessTokenOut = Depends(verify_token_driver_role))->APIResponse[PayoutBalanceOut]:
    """
    Get driver's current available balance for withdrawal.

    Returns the total earnings minus any pending/processed withdrawals.
    """
    # Get all payout records for this driver
    payouts = await retrieve_payouts(driverId=token.userId, start=0, stop=1000)

    # Calculate totals
    total_earnings = 0
    total_withdrawn = 0

    for payout in payouts:
        if payout.payoutOption == PayoutOptions.totalEarnings:
            total_earnings += payout.amount
        elif payout.payoutOption == PayoutOptions.withdrawalHistory:
            total_withdrawn += payout.amount

    available_balance = total_earnings - total_withdrawn

    return APIResponse(status_code=200, data=PayoutBalanceOut(
        total_earnings=total_earnings,
        total_withdrawn=total_withdrawn,
        available_balance=max(0, available_balance), # Ensure balance is never negative
        currency="GBP"
    ), detail="Balance calculated successfully")
# ------------------------------
# Request Payout (Transfer to Stripe Balance)
# ------------------------------
@router.post("/payout/request", response_model=APIResponse[PayoutOut])
async def request_payout_transfer(
    payout_request: PayoutRequestIn,
    token: accessTokenOut = Depends(verify_token_driver_role)
):
    """
    Request a payout transfer to driver's Stripe account.

    This will transfer money from platform to driver's Stripe balance.
    For instant payouts, money goes directly to bank (higher fees).
    """
    # Get driver details
    driver = await retrieve_driver_by_driver_id(id=token.userId)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # Check if driver has Stripe Connect account
    if not driver.stripeAccountId:
        raise HTTPException(
            status_code=400,
            detail="Driver must complete Stripe Connect onboarding first. Use /drivers/payout/onboard"
        )

    # Get available balance
    balance_response = await get_driver_available_balance(token)
    available_balance = balance_response.data.available_balance

    if payout_request.amount > available_balance:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient balance. Available: {available_balance}p, Requested: {payout_request.amount}p"
        )

    try:
        # Process the payout
        payout_result = await staff_payment_service.pay_driver(
            driver=driver,
            amount=payout_request.amount,
            description=payout_request.description,
            instant=payout_request.instant
        )

        # Record the payout in our system
        payout_record = PayoutCreate(
            payoutOption=PayoutOptions.withdrawalHistory,
            amount=payout_request.amount,
            driverId=token.userId,
            rideIds=[]  # This is a general payout, not tied to specific rides
        )
        new_payout = await add_payout(payout_record)

        return APIResponse(status_code=200, data=new_payout, detail="Payout processed successfully")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Payout failed: {str(e)}")

# ------------------------------
# Process Ride Earnings (Called after ride completion)
# ------------------------------
@router.post("/payout/earn", response_model=APIResponse[PayoutOut])
async def record_ride_earnings(
    ride_id: str = Body(..., description="ID of the completed ride"),
    earnings: int = Body(..., description="Earnings from this ride in pence", gt=0),
    token: accessTokenOut = Depends(verify_token_driver_role)
):
    """
    Record earnings from a completed ride.

    This is typically called automatically after ride completion,
    but can also be used for manual earnings recording.
    """
    # Verify the ride belongs to this driver
    rides = await retrieve_rides_by_driver_id(driver_id=token.userId)
    ride_found = next((r for r in rides if r.id == ride_id), None)

    if not ride_found:
        raise HTTPException(status_code=404, detail="Ride not found or doesn't belong to this driver")

    if ride_found.rideStatus != "COMPLETED":
        raise HTTPException(status_code=400, detail="Ride must be completed to record earnings")

    # Record the earnings
    payout_record = PayoutCreate(
        payoutOption=PayoutOptions.totalEarnings,
        amount=earnings,
        driverId=token.userId,
        rideIds=[ride_id]
    )

    new_payout = await add_payout(payout_record)

    return APIResponse(
        status_code=201,
        data=new_payout,
        detail="Ride earnings recorded successfully"
    )





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










# -------------------------------
# ---- RIDE STREAM EVENTS -------
# -------------------------------



