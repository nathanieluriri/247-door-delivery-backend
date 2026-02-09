
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
from security.account_status_checks import check_driver_account_status, check_driver_sse_eligibility
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
from core.redis_cache import async_redis
from services.sse_service import get_driver_presence, DRIVER_GEO_INDEX
from services.quarantine_service import log_quarantine_event
from core.antivirus import scan_bytes
from security.auth import verify_token_to_refresh, verify_token_driver_role
from security.encrypting_jwt import decode_jwt_token
from services.rating_service import add_rating, retrieve_rating_by_user_id
from services.ride_service import retrieve_rides_by_driver_id, retrieve_ride_by_ride_id, update_ride_by_id
from services.sse_service import publish_ride_request
from services.notification_targets import register_push_token, has_push_tokens
from schemas.notification import PushTokenRegister


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
@router.get(
    "/google/auth",
    summary="Start driver Google OAuth",
    description="Redirects the driver to Google OAuth to begin authentication.",
)
async def login(request: Request):
    """
    Begin Google OAuth login for drivers and redirect to the provider.

    Access: Public (no auth).
    """
    base_url = request.url_for("root")
    redirect_uri = f"{base_url}auth/callback"
     
    return await oauth.google_driver.authorize_redirect(request, redirect_uri)


# --- Step 2: Handle callback from Google ---
@router.get(
    "/auth/callback",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[DriverOut],
    summary="Driver Google OAuth callback",
    description="Handles Google OAuth callback, creates or authenticates the driver, and returns tokens.",
)
async def auth_callback(request: Request):
    """
    Handle Google OAuth callback for drivers and issue tokens.

    Access: Public (no auth).
    """
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



@router.get(
    "/",
    response_model_exclude={"data": {"__all__": {"password"}}},
    response_model=APIResponse[List[DriverOut]],
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="List drivers",
    description="Returns a paginated list of drivers.",
)
async def list_drivers(start:int= 0, stop:int=100):
    """
    List drivers (admin/system usage).

    Access: Driver only (valid driver access token required).
    """
    items = await retrieve_drivers(start=start,stop=stop)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.get(
    "/me",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[DriverOut],
    dependencies=[Depends(verify_token_driver_role)],
    response_model_exclude_none=True,
    summary="Get my driver profile",
    description="Returns the authenticated driver's profile details.",
)
async def get_driver_details(token:accessTokenOut = Depends(verify_token_driver_role)):
    """
    Fetch the authenticated driver's profile.

    Access: Driver only (valid driver access token required).
    """
 
    try:
        items = await retrieve_driver_by_driver_id(id=token.userId)
        return APIResponse(status_code=200, data=items, detail="users items fetched")
    except Exception as e:
        if str(e) == "'JWTPayload' object has no attribute 'userId'":
            raise HTTPException(status_code=401,detail=f"Invalid Token Use Driver Id if you want to access driver details with these tokens")
        raise HTTPException(status_code=500,detail=f"{e}")
     
@router.post(
    "/signup",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[DriverOut],
    summary="Register driver",
    description="Creates a new driver account using email and password.",
)
async def signup_new_driver(user_data:DriverCreate):
    """
    Register a new driver account.

    Access: Public (no auth).
    """
    if len(user_data.password)<8:
        raise HTTPException(status_code=401,detail="Password too short")
    items = await add_driver(driver_data=user_data)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.post(
    "/login",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[DriverOut],
    summary="Driver login",
    description="Authenticates a driver and returns access and refresh tokens.",
)
async def login_driver(user_data:DriverBase):
    """
    Authenticate a driver and return access/refresh tokens.

    Access: Public (no auth).
    """
    if len(user_data.password)<8:
        raise HTTPException(status_code=401,detail="Password too short")
    items = await authenticate_driver(user_data=user_data)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")



@router.post(
    "/refresh",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[DriverOut],
    dependencies=[Depends(verify_token_to_refresh)],
    summary="Refresh driver tokens",
    description="Refreshes an expired access token using a valid refresh token.",
)
async def refresh_driver_tokens(user_data:DriverRefresh,token:accessTokenOut = Depends(verify_token_to_refresh)):
    """
    Refresh an expired driver access token using a refresh token.

    Access: Driver only (expired access token in header + refresh token in body).
    """
    
    items= await refresh_driver_tokens_reduce_number_of_logins(user_refresh_data=user_data,expired_access_token=token.accesstoken)

    return APIResponse(status_code=200, data=items, detail="users items fetched")


@router.patch(
    "/profile",
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Update driver profile",
    description="Updates the authenticated driver's profile fields.",
)
async def update_driver_profile(driver_details:DriverUpdateProfile,token:accessTokenOut = Depends(verify_token_driver_role)):
    """
    Update the authenticated driver's profile fields.

    Access: Driver only (valid driver access token required).
    """
    driver =  await update_driver_by_id(driver_id=token.userId,driver_data=driver_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")
     


@router.post(
    "/location",
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status), Depends(check_driver_sse_eligibility)],
    summary="Update driver location",
    description="Updates the driver's real-time location coordinates.",
)
async def update_driver_current_location(
    payload: DriverLocationUpdate,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Update the driver's real-time location.

    Access: Driver only (valid driver access token + SSE eligibility required).
    """
    await update_driver_location(driver_id=token.userId, location=payload)
    return APIResponse(status_code=200, data=True, detail="Location updated")


@router.put(
    "/vehicle",
    response_model=APIResponse[DriverOut],
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Update driver vehicle",
    description="Updates the authenticated driver's vehicle information.",
)
async def update_driver_vehicle_details(
    payload: DriverVehicleUpdate,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Update the authenticated driver's vehicle details.

    Access: Driver only (valid driver access token required).
    """
    driver = await update_driver_vehicle(driver_id=token.userId, vehicle_details=payload)
    return APIResponse(status_code=200, data=driver, detail="Vehicle details updated")


@router.get(
    "/vehicle",
    response_model=APIResponse[dict],
    response_model_exclude_none=True,
    summary="Get driver vehicle info",
    description="Returns vehicle information for a driver using token or explicit driver_id.",
)
async def get_driver_vehicle_info(
    driver_id: Optional[str] = Query(default=None),
    token: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer_auth),
):
    """
    Fetch a driver's vehicle info (self or by explicit driver_id).

    Access: Driver (token) or Public with explicit `driver_id`.
    """
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
        "vehicleVerified": driver.vehicleVerified,
        "vehicleVerifiedAt": driver.vehicleVerifiedAt,
        "vehicleVerificationNotes": driver.vehicleVerificationNotes,
    }

    return APIResponse(status_code=200, data=vehicle_info, detail="Vehicle info retrieved")


# ---------------------------------
# ------- DOCUMENT UPLOAD ---------
# ---------------------------------


@router.post(
    "/documents/upload",
    response_model=APIResponse[DriverDocumentOut],
    dependencies=[Depends(verify_token_driver_role)],
    summary="Upload driver document",
    description="Uploads a compliance document and stores metadata for review.",
)
async def upload_driver_document(
    documentType: DocumentType = Form(...),
    file: UploadFile = File(...),
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Upload a driver compliance document. Storage backend is configurable
    (local or S3) and metadata is persisted in Mongo.

    Access: Driver only (valid driver access token required).
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
    summary="Upload file to Cloudflare",
    description="Uploads a file to the S3-compatible storage backend and returns signed URLs.",
)
async def upload_driver_file_to_cloudflare(
    file: UploadFile = File(...),
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Upload a file to the configured S3/Cloudflare storage backend.

    Access: Driver only (valid driver access token required).
    """
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
    summary="List driver documents",
    description="Returns all uploaded documents for the authenticated driver.",
)
async def list_my_documents(token: accessTokenOut = Depends(verify_token_driver_role)):
    """
    List all uploaded documents for the authenticated driver.

    Access: Driver only (valid driver access token required).
    """
    docs = await get_driver_documents(driver_id=token.userId)
    for d in docs:
        if getattr(d, "storageProvider", None) == "s3":
            d.signedUrl = get_signed_url(d.fileKey)
    return APIResponse(status_code=200, data=docs, detail="Documents fetched")


@router.get(
    "/documents/latest",
    response_model=APIResponse[List[DriverDocumentOut]],
    dependencies=[Depends(verify_token_driver_role)],
    summary="List latest driver documents",
    description="Returns the most recent document per type for the authenticated driver.",
)
async def list_my_latest_documents_by_type(token: accessTokenOut = Depends(verify_token_driver_role)):
    """
    List the most recent document per type for the authenticated driver.

    Access: Driver only (valid driver access token required).
    """
    docs = await list_latest_documents_for_driver(driver_id=token.userId)
    for d in docs:
        if getattr(d, "storageProvider", None) == "s3":
            d.signedUrl = get_signed_url(d.fileKey)
    return APIResponse(status_code=200, data=docs, detail="Latest documents fetched")


@router.get(
    "/documents/{docId}/verify",
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_token_driver_role)],
    summary="Verify document integrity",
    description="Verifies stored document integrity using the recorded SHA256 hash.",
)
async def verify_document_integrity(docId: str, token: accessTokenOut = Depends(verify_token_driver_role)):
    """
    Verify integrity of a stored document using its SHA256 hash.

    Access: Driver only (valid driver access token required).
    """
    doc = await retrieve_driver_document(docId)
    if not doc or doc.driverId != token.userId:
        raise HTTPException(status_code=404, detail="Document not found")
    ok = verify_integrity(doc.fileKey, doc.sha256)
    return APIResponse(status_code=200, data=ok, detail="Integrity verified" if ok else "Integrity check failed")



@router.delete(
    "/account",
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Delete driver account",
    description="Deletes the authenticated driver's account and associated data.",
)
async def delete_user_account(token:accessTokenOut = Depends(verify_token_driver_role)):
    """
    Delete the authenticated driver's account.

    Access: Driver only (valid driver access token required).
    """
    result = await remove_driver(driver_id=token.userId)
    return APIResponse(data=result,status_code=200,detail="Successfully deleted account")

@router.post(
    "/logout",
    dependencies=[Depends(verify_token_driver_role)],
    summary="Logout driver",
    description="Invalidates the driver's access and refresh tokens.",
)
async def logout_driver(token: accessTokenOut = Depends(verify_token_driver_role)):
    """
    Invalidate access and refresh tokens for the driver.

    Access: Driver only (valid driver access token required).
    """
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

@router.get(
    "/rating",
    response_model_exclude={"data": {"__all__": {"password"}}},
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Get driver rating",
    description="Returns rating summary for the authenticated driver.",
)
async def view_rating(token:accessTokenOut = Depends(verify_token_driver_role)):
    """
    Retrieve the authenticated driver's rating summary.

    Access: Driver only (valid driver access token required).
    """
    rating = await retrieve_rating_by_user_id(user_id=token.userId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.get(
    "/rider/{riderId}/rating",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Get rider rating",
    description="Returns rating summary for a rider by ID.",
)
async def view_rider_rating(riderId:str):
    """
    Retrieve a rider's rating by rider ID.

    Access: Driver only (valid driver access token required).
    """
    rating = await retrieve_rating_by_user_id(user_id=riderId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Retrieved User Rating")

@router.post(
    "/rate/rider",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Rate a rider",
    description="Submits a rating for a rider after a completed ride.",
)
async def rate_rider_after_ride(rating_data:RatingBase,token:accessTokenOut = Depends(verify_token_driver_role)):
    """
    Submit a rating for a rider after a completed ride.

    Access: Driver only (valid driver access token required).
    """
    

    
    rider_rating = RatingCreate(**rating_data.model_dump(),raterId=token.userId)
    rating = await add_rating(rating_data=rider_rating,driverId=token.userId)
    return APIResponse(data=rating,status_code=200,detail="Successfully Rated Rider")



# -------------------------------
# ------- RIDE MANAGEMENT ------- 
# -------------------------------




@router.post(
    "/ride/{ride_id}/accept",
    dependencies=[Depends(check_driver_sse_eligibility)],
    summary="Accept a ride",
    description="Assigns the authenticated driver to a ride and updates ride status.",
)
async def accept_ride(
    ride_id: str,
    token: accessTokenOut = Depends(verify_token_driver_role), 
):
    """
    Accept a ride request and transition ride status.

    Access: Driver only (valid driver access token + SSE eligibility required).
    """
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


@router.post(
    "/push/register",
    response_model=APIResponse[list[str]],
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Register driver push token",
    description="Registers a OneSignal player ID for push notifications.",
)
async def register_driver_push_token(
    payload: PushTokenRegister,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    tokens = await register_push_token(
        user_type="driver",
        user_id=token.userId,
        player_id=payload.player_id,
    )
    return APIResponse(status_code=200, data=tokens, detail="Push token registered")


@router.get(
    "/push/status",
    response_model=APIResponse[dict],
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Driver push status",
    description="Returns whether the driver has any push tokens registered.",
)
async def get_driver_push_status(
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    enabled = await has_push_tokens("driver", token.userId)
    return APIResponse(
        status_code=200,
        data={"enabled": enabled},
        detail="Push status retrieved",
    )


@router.post(
    "/ride/{ride_id}/start",
    dependencies=[Depends(check_driver_sse_eligibility)],
    summary="Start a ride",
    description="Transitions ride from arrivingToPickup to drivingToDestination.",
)
async def start_ride(
    ride_id: str,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Start a ride and transition ride status.

    Access: Driver only (valid driver access token + SSE eligibility required).
    """
    ride_update = RideUpdate(
        rideStatus=RideStatus.drivingToDestination
    )

    updated_ride = await update_ride_by_id(
        ride_id=ride_id,
        ride_data=ride_update,
        driver_id=token.userId
    )

    return APIResponse(
        status_code=200,
        data=updated_ride,
        detail="Ride started successfully"
    )


@router.post(
    "/ride/{ride_id}/complete",
    dependencies=[Depends(check_driver_sse_eligibility)],
    summary="Complete a ride",
    description="Transitions ride from drivingToDestination to completed.",
)
async def complete_ride(
    ride_id: str,
    token: accessTokenOut = Depends(verify_token_driver_role),
):
    """
    Complete a ride and transition ride status.

    Access: Driver only (valid driver access token + SSE eligibility required).
    """
    ride_update = RideUpdate(
        rideStatus=RideStatus.completed
    )

    updated_ride = await update_ride_by_id(
        ride_id=ride_id,
        ride_data=ride_update,
        driver_id=token.userId
    )

    return APIResponse(
        status_code=200,
        data=updated_ride,
        detail="Ride completed successfully"
    )
    
    
@router.post(
    "/ride/{ride_id}",
    summary="Get ride details",
    description="Fetches ride details for the authenticated driver.",
)
async def retrieve_ride_details(
    ride_id: str,
    token: accessTokenOut = Depends(verify_token_driver_role), 
):
    """
    Fetch ride details by ride ID for the authenticated driver.

    Access: Driver only (valid driver access token required).
    """
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



@router.get(
    "/ride/history",
    response_model_exclude_none=True,
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Get driver ride history",
    description="Returns past rides for the authenticated driver.",
)
async def ride_history(token:accessTokenOut = Depends(verify_token_driver_role)):
    """
    List ride history for the authenticated driver.

    Access: Driver only (valid driver access token required).
    """
    
    rides = await retrieve_rides_by_driver_id(driver_id=token.userId)
    return APIResponse(status_code=200,data= rides, detail="Successfully Retrieved Ride history for driver")

 
 
# -----------------------------------
# ------- PASSWORD MANAGEMENT ------- 
# -----------------------------------

 
@router.patch(
    "/password-reset",
    dependencies=[Depends(verify_token_driver_role), Depends(check_driver_account_status)],
    summary="Change driver password",
    description="Updates the authenticated driver's password.",
)
async def update_driver_password_while_logged_in(driver_details:DriverUpdatePassword,token:accessTokenOut = Depends(verify_token_driver_role)):
    """
    Change the authenticated driver's password.

    Access: Driver only (valid driver access token required).
    """
    driver =  await update_driver_by_id(driver_id=token.userId,driver_data=driver_details,is_password_getting_changed=True)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")



@router.post(
    "/password-reset/request",
    response_model=APIResponse[ResetPasswordInitiationResponse],
    summary="Request driver password reset",
    description="Initiates the password reset flow by sending an OTP.",
)
async def start_password_reset_process_for_driver_that_forgot_password(driver_details:ResetPasswordInitiation):
    """
    Start the driver password reset flow (send OTP).

    Access: Public (no auth).
    """
    driver =  await driver_reset_password_intiation(driver_details=driver_details)   
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")



@router.patch(
    "/password-reset/confirm",
    summary="Confirm driver password reset",
    description="Completes password reset with OTP and new password.",
)
async def finish_password_reset_process_for_driver_that_forgot_password(driver_details:ResetPasswordConclusion):
    """
    Complete the driver password reset using an OTP or token.

    Access: Public (no auth).
    """
    driver =  await driver_reset_password_conclusion(driver_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")




# ---------------------------------
# ------- PAYOUT MANAGEMENT ------- 
# ---------------------------------

staff_payment_service = get_staff_payment_service()



# ------------------------------
# Driver Stripe Connect Onboarding
# ------------------------------
@router.post(
    "/payout/onboard",
    response_model=APIResponse[dict],
    summary="Start payout onboarding",
    description="Creates a Stripe Connect account and returns an onboarding link.",
)
async def onboard_driver_for_payments(token: accessTokenOut = Depends(verify_token_driver_role)):
    """
    Onboard driver for Stripe Connect payments.

    Creates a Stripe Connect Express account and generates onboarding link.
    Driver must complete onboarding before receiving payments.

    Access: Driver only (valid driver access token required).
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
@router.get(
    "/payout/status",
    response_model=APIResponse[dict],
    summary="Get payout status",
    description="Returns Stripe Connect account status and payout eligibility.",
)
async def get_driver_payment_status(token: accessTokenOut = Depends(verify_token_driver_role)):
    """
    Get driver's current payment status and eligibility.

    Returns information about Stripe Connect account status and payout eligibility.

    Access: Driver only (valid driver access token required).
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

@router.get(
    "/payouts",
    response_model=APIResponse[List[PayoutOut]],
    summary="List driver payouts",
    description="Returns payout records for the authenticated driver with pagination.",
)
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

    Access: Driver only (valid driver access token required).
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
@router.get(
    "/payout/{id}",
    response_model=APIResponse[PayoutOut],
    summary="Get payout by ID",
    description="Fetches a single payout record by its ID.",
)
async def view_information_regarding_a_previous_payout(
    
    id: str = Path(..., description="payout ID to fetch specific item"),
    
    token:accessTokenOut = Depends(verify_token_driver_role)
    
):
    """
    Retrieves a single Payout by its ID.

    Access: Driver only (valid driver access token required).
    """
    item = await retrieve_payout_by_payout_id(id=id,driverId=token.userId)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payout not found")
    
    return APIResponse(status_code=200, data=item, detail="payout item fetched")



 



@router.get(
    "/payout/balance",
    response_model=APIResponse[PayoutBalanceOut],
    summary="Get payout balance",
    description="Computes available balance based on earnings and withdrawals.",
)
async def get_driver_available_balance(token: accessTokenOut = Depends(verify_token_driver_role))->APIResponse[PayoutBalanceOut]:
    """
    Get driver's current available balance for withdrawal.

    Returns the total earnings minus any pending/processed withdrawals.

    Access: Driver only (valid driver access token required).
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
@router.post(
    "/payout/request",
    response_model=APIResponse[PayoutOut],
    summary="Request a payout",
    description="Transfers funds to the driver's Stripe balance and records the payout.",
)
async def request_payout_transfer(
    payout_request: PayoutRequestIn,
    token: accessTokenOut = Depends(verify_token_driver_role)
):
    """
    Request a payout transfer to driver's Stripe account.

    This will transfer money from platform to driver's Stripe balance.
    For instant payouts, money goes directly to bank (higher fees).

    Access: Driver only (valid driver access token required).
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
@router.post(
    "/payout/earn",
    response_model=APIResponse[PayoutOut],
    summary="Record ride earnings",
    description="Records earnings from a completed ride to the driver payout ledger.",
)
async def record_ride_earnings(
    ride_id: str = Body(..., description="ID of the completed ride"),
    earnings: int = Body(..., description="Earnings from this ride in pence", gt=0),
    token: accessTokenOut = Depends(verify_token_driver_role)
):
    """
    Record earnings from a completed ride.

    This is typically called automatically after ride completion,
    but can also be used for manual earnings recording.

    Access: Driver only (valid driver access token required).
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


@router.get(
    "/locations/active",
    response_model=APIResponse[list[dict]],
    summary="List active driver locations",
    description="Returns current latitude/longitude for active drivers with valid presence.",
)
async def list_active_driver_locations():
    driver_ids = await async_redis.zrange(DRIVER_GEO_INDEX, 0, -1)
    results: list[dict] = []
    for driver_id in driver_ids:
        meta = await get_driver_presence(driver_id)
        if not meta:
            continue
        if meta.get("account_status") not in {"active"}:
            continue
        lat = meta.get("latitude")
        lng = meta.get("longitude")
        if lat is None or lng is None:
            continue
        results.append(
            {
                "driver_id": driver_id,
                "latitude": lat,
                "longitude": lng,
                "last_seen": meta.get("last_seen"),
                "vehicle_type": meta.get("vehicle_type"),
            }
        )
    return APIResponse(
        status_code=200,
        data=results,
        detail="Active driver locations",
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
