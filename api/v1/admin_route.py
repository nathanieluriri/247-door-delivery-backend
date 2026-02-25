from fastapi import APIRouter, HTTPException, Query, Request, status, Path,Depends,Body
from typing import List,Annotated
from core.routing_config import maps
from core.admin_logger import log_what_admin_does
from core.payments import PaymentService, get_payment_service
from repositories.admin_activity_repo import list_admin_activity_logs
from core.vehicles import Vehicle
from schemas.driver import DriverOut, DriverUpdateAccountStatus, DriverUpdate, DriverVehicleVerificationUpdate
from schemas.driver_document import DocumentStatus, DriverDocumentUpdateStatus, DocumentType, DriverDocumentsByUser, DocumentSortBy, SortDirection
from schemas.background_check import BackgroundStatus
from schemas.background_provider import BackgroundProviderPayload
from schemas.place import Location
from schemas.response_schema import APIResponse
from schemas.ride import RideBase, RideCreate, RideOut, RideUpdate
from schemas.rider_schema import RiderOut, RiderUpdateAccountStatus
from schemas.tokens_schema import accessTokenOut
from schemas.user_schema import UserOut
from celery_worker import celery_app
from schemas.admin_schema import (
    AdminCreate,
    AdminOut,
    AdminBase,
    AdminUpdate,
    AdminRefresh,
    AdminLogin,
    AdminUpdatePassword
)
from security.account_status_checks import check_admin_account_status_and_permissions
from services.admin_service import (
    add_admin,
    admin_reset_password_conclusion,
    admin_reset_password_initiation,
    remove_admin,
    retrieve_admins,
    authenticate_admin,
    retrieve_admin_by_admin_id,
    update_admin_by_id,
    refresh_admin_tokens_reduce_number_of_logins,
    search_users_for_admin,

)
from services.driver_service import (
    update_driver_by_id,
    update_driver_by_id_admin_func,
    
)
from services.driver_document_service import set_driver_document_status, list_pending_documents_grouped_by_driver
from services.background_check_service import record_background_result, list_background_checks_service, auto_link_documents_to_background
from services.audit_log_service import record_audit_event
from services.place_service import calculate_fare_using_vehicle_config_and_distance, get_place_details
from services.ride_service import add_ride, add_ride_admin_func, retrieve_ride_by_ride_id, retrieve_rides_by_driver_id, retrieve_rides_by_user_id,update_ride_by_id_admin_func
from services.rider_service import (
    ban_riders,
    update_rider_by_id,
    RiderUpdate,
    retrieve_riders_by_email_and_status,
    
)
from schemas.imports import *
from security.auth import verify_token,verify_token_to_refresh,verify_admin_token
from services.driver_service import retrieve_driver_by_driver_id, retrieve_drivers
from services.rider_service import retrieve_rider_by_rider_id, retrieve_riders
from fastapi.routing import APIRoute

 
            
router = APIRouter(prefix="/admins", tags=["Admins"])

 
@router.get(
    "/", 
    response_model=APIResponse[List[AdminOut]],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"__all__": {"password"}}},
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="List admins",
    description="Returns a paginated list of admin accounts.",
)
async def list_admins(
    
    # Use Path and Query for explicit documentation/validation of GET parameters
    start: Annotated[
        int,
        Query(ge=0, description="The starting index (offset) for the list of admins.")
    ] , 
    stop: Annotated[
        int, 
        Query(gt=0, description="The ending index for the list of admins (limit).")
    ]
):
    """
    **ADMIN ONLY:** Retrieves a paginated list of all registered admins.

    **Authorization:** Requires a **valid Access Token** (Admin role) in the 
    `Authorization: Bearer <token>` header.

    ### Examples (Illustrative URLs):

    * **First Page:** `/admins/0/5` (Start at index 0, retrieve up to 5 admins)
    * **Second Page:** `/admins/5/10` (Start at index 5, retrieve up to 5 more admins)

    Access: Admin only (valid admin access token required).
    
    """
    
    items = await retrieve_admins(start=start, stop=stop)
    
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.get(
    "/profile",
    response_model=APIResponse[AdminOut],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"password"}},
    summary="Get my admin profile",
    description="Returns the authenticated admin's profile details.",
)
async def get_my_admin(
    token: accessTokenOut = Depends(verify_admin_token),
        
):
    """
    Retrieves the profile information for the currently authenticated admin.

    The admin's ID is automatically extracted from the valid Access Token 
    in the **Authorization: Bearer <token>** header.

    Access: Admin only (valid admin access token required).
    """
    
    items = await retrieve_admin_by_admin_id(id=token.get("userId"))
    return APIResponse(status_code=200, data=items, detail="admins items fetched")





@router.post(
    "/signup",
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[AdminOut],
    summary="Create admin account",
    description="Creates a new admin account and records the inviter.",
)
async def signup_new_admin(
    admin_data:AdminBase,
    token: accessTokenOut = Depends(verify_admin_token),
):
    """
    Create a new admin account (requires admin privileges).

    Access: Admin only (valid admin access token required).
    """
 
    admin_data_dict = admin_data.model_dump() 
    new_admin = AdminCreate(
      invited_by=token.get("userId"),
        **admin_data_dict
    )
    items = await add_admin(admin_data=new_admin)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")

@router.post(
    "/login",
    response_model_exclude={"data": {"password"}},
    response_model_exclude_none=True,
    response_model=APIResponse[AdminOut],
    summary="Admin login",
    description="Authenticates an admin and returns access and refresh tokens.",
)
async def login_admin(
    
    admin_data:AdminLogin,

):
    """
    Authenticates a admin with the provided email and password.
    
    Upon success, returns the authenticated admin data and an authentication token.

    Access: Public (no auth).
    """
    items = await authenticate_admin(admin_data=admin_data)
    # The `authenticate_admin` function should raise an HTTPException 
    # (e.g., 401 Unauthorized) on failure.
    
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")



@router.post(
    "/refresh",
    response_model=APIResponse[AdminOut],
    dependencies=[Depends(verify_token_to_refresh)],
    response_model_exclude={"data": {"password"}},
    summary="Refresh admin tokens",
    description="Refreshes an expired access token using a valid refresh token.",
)
async def refresh_admin_tokens(
    admin_data: Annotated[
        AdminRefresh,
        Body(
            openapi_examples={
                "successful_refresh": {
                    "summary": "Successful Token Refresh",
                    "description": (
                        "The correct payload for refreshing tokens. "
                        "The **expired access token** is provided in the `Authorization: Bearer <token>` header."
                    ),
                    "value": {
                        # A long-lived, valid refresh token
                        "refresh_token": "valid.long.lived.refresh.token.98765"
                    },
                },
                "invalid_refresh_token": {
                    "summary": "Invalid Refresh Token",
                    "description": (
                        "Payload that would fail the refresh process because the **refresh_token** "
                        "in the body is invalid or has expired."
                    ),
                    "value": {
                        "refresh_token": "expired.or.malformed.refresh.token.00000"
                    },
                },
                "mismatched_tokens": {
                    "summary": "Tokens Belong to Different Admins",
                    "description": (
                        "A critical security failure example: the refresh token in the body "
                        "does not match the admin ID associated with the expired access token in the header. "
                        "This should result in a **401 Unauthorized**."
                    ),
                    "value": {
                        "refresh_token": "refresh.token.of.different.admin.77777"
                    },
                },
            }
        ),
    ],
    token: accessTokenOut = Depends(verify_token_to_refresh)
):
    """
    Refreshes the admin's access token and returns a new token pair.

    Requires an **expired access token** in the Authorization header and a **valid refresh token** in the body.

    Access: Admin only (expired access token + refresh token required).
    """
 
    items = await refresh_admin_tokens_reduce_number_of_logins(
        admin_refresh_data=admin_data,
        expired_access_token=token.accesstoken
    )
    
    # Clears the password before returning, which is good practice.
    items.password = ''
    
    return APIResponse(status_code=200, data=items, detail="admins items fetched")


@router.delete(
    "/account",
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does)],
    response_model_exclude_none=True,
    summary="Delete admin account",
    description="Deletes the authenticated admin account.",
)
async def delete_admin_account(
    token: dict = Depends(verify_admin_token),
 
):
    """
    Deletes the account associated with the provided access token.

    The admin ID is extracted from the valid Access Token in the Authorization header.
    No request body is required.

    Access: Admin only (valid admin access token required).
    """
    admin_id = token.get("userId") or token.get("user_id")
    if not admin_id:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    result = await remove_admin(admin_id=admin_id)
    
    # The 'result' is assumed to be a standard FastAPI response object or a dict/model 
    # that is automatically converted to a response.
    return result


@router.patch(
    "/profile",
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="Update admin profile",
    description="Updates the authenticated admin profile fields.",
)
async def update_driver_profile(admin_details:AdminUpdate,token:dict = Depends(verify_admin_token)):
    """
    Update the authenticated admin profile.

    Access: Admin only (valid admin access token required).
    """
    admin_id = token.get("userId") or token.get("user_id")
    if not admin_id:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    admin = await update_admin_by_id(admin_id=admin_id,admin_data=admin_details,)
    return APIResponse(data=admin,status_code=200,detail="Succesfully updated profile")


@router.get(
    "/users/search",
    response_model=APIResponse[List[UserOut]],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="Search users",
    description="Searches riders and drivers by email or exact user ID.",
)
async def search_users_for_admin_autocomplete(
    q: str = Query(..., min_length=1, description="Email or user id to search"),
    limit: int = Query(default=10, ge=1, le=50, description="Max results to return"),
):
    """
    Search riders and drivers by email (autocomplete) or exact user id.

    Access: Admin only (valid admin access token required).
    """
    results = await search_users_for_admin(query=q, limit=limit)
    return APIResponse(status_code=200, data=results, detail="Users retrieved")


@router.get(
    "/logs",
    response_model=APIResponse[list],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="List admin activity logs",
    description="Returns admin activity logs captured by the log_what_admin_does dependency.",
)
async def list_admin_activity_logs_endpoint(
    limit: int = Query(default=100, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
    admin_id: str | None = Query(default=None, description="Filter by admin ID"),
    method: str | None = Query(default=None, description="Filter by HTTP method"),
    path: str | None = Query(default=None, description="Filter by request path"),
    from_ts: int | None = Query(default=None, description="Filter logs from unix timestamp (inclusive)"),
    to_ts: int | None = Query(default=None, description="Filter logs up to unix timestamp (inclusive)"),
):
    """
    Returns a list of admin activity logs (most recent first).

    Storage: Persisted in MongoDB without expiration.
    Access: Admin only (valid admin access token required).
    """
    logs = await list_admin_activity_logs(
        admin_id=admin_id,
        method=method,
        path=path,
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
        skip=skip,
    )
    return APIResponse(status_code=200, data=logs, detail="Admin logs fetched")

# ---------------------------------------------------
# --------------- DRIVER MANAGEMENT -----------------
# ---------------------------------------------------

@router.get(
    "/drivers/",
    response_model_exclude={"data": {"__all__": {"password"}}},
    response_model_exclude_none=True,
    response_model=APIResponse[List[DriverOut]],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="List drivers (admin)",
    description="Returns a paginated list of drivers for administrative use.",
)
async def list_of_drivers(start:int= 0, stop:int=100,token:accessTokenOut = Depends(verify_admin_token)):
    """
    List drivers with pagination (admin only).

    Access: Admin only (valid admin access token required).
    """
    items = await retrieve_drivers(start=start,stop=stop)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")

@router.get(
    "/driver/{driverId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[DriverOut],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does)],
    response_model_exclude_none=True,
    summary="Get driver by ID (admin)",
    description="Fetches a driver's profile by driver ID.",
)
async def get_a_particular_driver_details(driverId:str,token:accessTokenOut = Depends(verify_admin_token)):
    """
    Fetch a driver profile by ID (admin only).

    Access: Admin only (valid admin access token required).
    """
    try: 
        items = await retrieve_driver_by_driver_id(id=driverId)
        return APIResponse(status_code=200, data=items, detail="users items fetched")
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"{e}")
    
@router.patch(
    "/ban/driver/{driverId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Ban driver",
    description="Bans a driver account and records an audit event.",
)
async def ban_a_driver_from_using_the_app(driverId:str,token:accessTokenOut = Depends(verify_admin_token)):
    """
    Ban a driver account (admin only).

    Access: Admin only (valid admin access token required).
    """
    driver_data = DriverUpdateAccountStatus(accountStatus=AccountStatus.BANNED)
    celery_app.send_task(
                "celery_worker.run_async_task",
                args=[
                    "ban_drivers",       # function path
                    {"user_id": driverId,"user":driver_data.model_dump()} # kwargs
                        ]
                    )
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="ban_driver",
        target_type="driver",
        target_id=driverId,
        metadata={"reason": "admin_ban_request"},
    )
    
    return APIResponse(status_code=200,data=True,detail="Successfully banned driver from the app")


@router.patch(
    "/suspend/driver/{driverId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Suspend driver",
    description="Temporarily suspends a driver account and records an audit event.",
)
async def suspend_driver_from_using_the_app(driverId: str, token: accessTokenOut = Depends(verify_admin_token)):
    driver_data = DriverUpdateAccountStatus(accountStatus=AccountStatus.SUSPENDED)
    celery_app.send_task(
        "celery_worker.run_async_task",
        args=[
            "ban_drivers",
            {"user_id": driverId, "user": driver_data.model_dump()},
        ],
    )
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="suspend_driver",
        target_type="driver",
        target_id=driverId,
        metadata={"reason": "admin_suspend_request"},
    )
    return APIResponse(status_code=200, data=True, detail="Successfully suspended driver from the app")


@router.patch(
    "/deactivate/driver/{driverId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Deactivate driver",
    description="Deactivates a driver account (soft disable) and records an audit event.",
)
async def deactivate_driver_account(driverId: str, token: accessTokenOut = Depends(verify_admin_token)):
    driver_data = DriverUpdateAccountStatus(accountStatus=AccountStatus.DEACTIVATED)
    update = await update_driver_by_id_admin_func(driver_id=driverId, driver_data=driver_data)
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="deactivate_driver",
        target_type="driver",
        target_id=driverId,
        metadata={"reason": "admin_deactivate_request"},
    )
    return APIResponse(status_code=200, data=True, detail="Successfully deactivated driver account")

 

@router.patch(
    "/approve/driver/{driverId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[DriverOut],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Approve driver",
    description="Approves a driver account and sets it to active.",
)
async def approve_a_driver_to_use_the_driver_app(driverId:str,token:accessTokenOut = Depends(verify_admin_token)):
    """
    Approve a driver account and set it to active.

    Access: Admin only (valid admin access token required).
    """
    driver_data = DriverUpdateAccountStatus(accountStatus=AccountStatus.ACTIVE)
    update =await update_driver_by_id_admin_func(driver_id=driverId,driver_data=driver_data)
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="approve_driver",
        target_type="driver",
        target_id=driverId,
        metadata={"status": "active"},
    )
    return APIResponse(status_code=200,data=update,detail="Successfully Approved this driver so they can use the app")


@router.patch(
    "/driver/{driverId}/documents/{docId}",
    response_model=APIResponse[dict],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="Review driver document",
    description="Approves or rejects a driver document and records an audit event.",
)
async def review_driver_document(
    driverId: str,
    docId: str,
    status: DocumentStatus = Body(..., embed=True),
    reason: str | None = Body(default=None, embed=True),
    token: accessTokenOut = Depends(verify_admin_token),
):
    """
    Approve or reject a driver's uploaded document.

    Access: Admin only (valid admin access token required).
    """
    update = DriverDocumentUpdateStatus(status=status, reason=reason)
    updated = await set_driver_document_status(docId, update)
    # auto-link to background when approved
    if status == DocumentStatus.APPROVED:
        try:
            await auto_link_documents_to_background(driverId)
        except Exception:
            pass
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="review_driver_document",
        target_type="driver_document",
        target_id=docId,
        metadata={"status": status, "driverId": driverId, "reason": reason},
    )
    return APIResponse(status_code=200, data={"document": updated}, detail="Document status updated")


@router.patch(
    "/driver/{driverId}/vehicle/verify",
    response_model=APIResponse[DriverOut],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="Verify driver vehicle",
    description="Updates the driver's vehicle verification status and notes.",
)
async def verify_driver_vehicle_information(
    driverId: str,
    payload: DriverVehicleVerificationUpdate,
    token: accessTokenOut = Depends(verify_admin_token),
):
    """
    Update vehicle verification status and notes for a driver.

    Access: Admin only (valid admin access token required).
    """
    update = DriverUpdate(
        vehicleVerified=payload.vehicleVerified,
        vehicleVerifiedAt=payload.vehicleVerifiedAt,
        vehicleVerificationNotes=payload.vehicleVerificationNotes,
    )
    updated = await update_driver_by_id(driver_id=driverId, driver_data=update)
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="verify_driver_vehicle",
        target_type="driver",
        target_id=driverId,
        metadata={
            "vehicleVerified": payload.vehicleVerified,
            "vehicleVerificationNotes": payload.vehicleVerificationNotes,
        },
    )
    return APIResponse(status_code=200, data=updated, detail="Driver vehicle verification updated")


@router.get(
    "/driver-documents/pending",
    response_model=APIResponse[List[DriverDocumentsByUser]],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="List pending driver documents",
    description="Returns pending driver documents grouped by driver and document type.",
)
async def list_pending_driver_documents_by_type(
    documentType: DocumentType = Query(...),
    driverId: str | None = Query(default=None),
    sortBy: DocumentSortBy = Query(default=DocumentSortBy.uploadedAt),
    sortDir: SortDirection = Query(default=SortDirection.desc),
):
    """
    List pending driver documents grouped by driver and type.

    Access: Admin only (valid admin access token required).
    """
    grouped = await list_pending_documents_grouped_by_driver(documentType, driverId, sortBy, sortDir)
    return APIResponse(status_code=200, data=grouped, detail="Pending documents fetched")


@router.patch(
    "/driver/{driverId}/background",
    response_model=APIResponse[dict],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="Update background check",
    description="Records a background check decision for a driver.",
)
async def update_background_check(
    driverId: str,
    status: BackgroundStatus = Body(..., embed=True),
    notes: str | None = Body(default=None, embed=True),
    referenceId: str | None = Body(default=None, embed=True),
    token: accessTokenOut = Depends(verify_admin_token),
):
    """
    Record an admin-reviewed background check status for a driver.

    Access: Admin only (valid admin access token required).
    """
    updated = await record_background_result(
        driver_id=driverId, status=status, notes=notes, reference=referenceId
    )
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="background_check_update",
        target_type="driver",
        target_id=driverId,
        metadata={"status": status, "referenceId": referenceId, "notes": notes},
    )
    return APIResponse(status_code=200, data={"background": updated}, detail="Background check updated")


@router.post(
    "/driver/{driverId}/background/provider",
    response_model=APIResponse[dict],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="Ingest background provider update",
    description="Ingests background check results from a third-party provider.",
)
async def ingest_background_check_from_provider(
    driverId: str,
    payload: BackgroundProviderPayload,
    token: accessTokenOut = Depends(verify_admin_token),
):
    """
    Ingest a background check status update from an external provider.

    Access: Admin only (valid admin access token required).
    """
    updated = await record_background_result(
        driver_id=driverId,
        status=payload.status,
        notes=payload.notes,
        reference=payload.referenceId,
    )
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="background_provider_update",
        target_type="driver",
        target_id=driverId,
        metadata={"provider": payload.provider, "raw": payload.raw},
    )
    return APIResponse(status_code=200, data={"background": updated}, detail="Background provider update applied")


@router.get(
    "/background-checks",
    response_model=APIResponse[list],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="List background checks",
    description="Returns all background check records.",
)
async def list_all_background_checks():
    """
    List all recorded background checks (admin only).

    Access: Admin only (valid admin access token required).
    """
    checks = await list_background_checks_service()
    return APIResponse(status_code=200, data=checks, detail="Background checks fetched")
    
# --------------------------------------------------
# --------------- RIDER MANAGEMENT -----------------
# --------------------------------------------------



@router.get(
    "/riders/",
    response_model_exclude={"data": {"__all__": {"password"}}},
    response_model_exclude_none=True,
    response_model=APIResponse[List[RiderOut]],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="List riders (admin)",
    description="Returns a paginated list of riders for administrative use.",
)
async def list_riders(start:int= 0, stop:int=100,token:accessTokenOut = Depends(verify_admin_token)):
    """
    List riders with pagination (admin only).

    Access: Admin only (valid admin access token required).
    """
    items = await retrieve_riders(start=0,stop=100)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.get(
    "/riders/search",
    response_model=APIResponse[List[UserOut]],
    response_model_exclude_none=True,
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="Search riders",
    description="Searches riders by email and/or account status.",
)
async def search_riders_by_email_and_status(
    email_address: str | None = Query(default=None, description="Filter by rider email (partial match)"),
    status: AccountStatus | None = Query(default=None, description="Filter by account status"),
    start: int = Query(default=0, ge=0),
    stop: int = Query(default=100, ge=1),
):
    """
    Search riders by email and/or account status (admin only).

    Access: Admin only (valid admin access token required).
    """
    riders = await retrieve_riders_by_email_and_status(
        email_address=email_address,
        status=status,
        start=start,
        stop=stop,
    )
    results = [
        UserOut(
            id=rider.id,
            email=rider.email,
            firstName=rider.firstName,
            lastName=rider.lastName,
            accountStatus=rider.accountStatus,
            userType=UserType.rider,
        )
        for rider in riders
    ]
    return APIResponse(status_code=200, data=results, detail="Riders retrieved")



@router.get(
    "/rider/{riderId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[RiderOut],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Get rider by ID (admin)",
    description="Fetches a rider profile by rider ID.",
)
async def get_a_particular_riders_details(riderId:str,token:accessTokenOut = Depends(verify_admin_token)):
    """
    Fetch a rider profile by ID (admin only).

    Access: Admin only (valid admin access token required).
    """
    rider = await retrieve_rider_by_rider_id(id=riderId)
    return APIResponse(status_code=200, data=rider, detail="rider fetched")

 
@router.patch(
    "/ban/rider/{riderId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Ban rider",
    description="Bans a rider account and records an audit event.",
)
async def ban_a_rider_from_using_the_app(riderId:str,token:accessTokenOut = Depends(verify_admin_token)):
    """
    Ban a rider account (admin only).

    Access: Admin only (valid admin access token required).
    """
    rider_data = RiderUpdateAccountStatus(accountStatus=AccountStatus.BANNED) 

    celery_app.send_task(
                "celery_worker.run_async_task",
                args=[
                    "ban_riders",       # function path
                    {"user_id": riderId,"user":rider_data.model_dump()} # kwargs
                        ]
                    )
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="ban_rider",
        target_type="rider",
        target_id=riderId,
        metadata={"reason": "admin_ban_request"},
    )
    
    return APIResponse(status_code=200,data=True,detail="Successfully banned Rider from the app")


@router.patch(
    "/suspend/rider/{riderId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Suspend rider",
    description="Temporarily suspends a rider account and records an audit event.",
)
async def suspend_rider_from_using_the_app(riderId: str, token: accessTokenOut = Depends(verify_admin_token)):
    rider_data = RiderUpdateAccountStatus(accountStatus=AccountStatus.SUSPENDED)
    celery_app.send_task(
        "celery_worker.run_async_task",
        args=[
            "ban_riders",
            {"user_id": riderId, "user": rider_data.model_dump()},
        ],
    )
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="suspend_rider",
        target_type="rider",
        target_id=riderId,
        metadata={"reason": "admin_suspend_request"},
    )
    return APIResponse(status_code=200, data=True, detail="Successfully suspended rider from the app")


@router.patch(
    "/deactivate/rider/{riderId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[bool],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Deactivate rider",
    description="Deactivates a rider account (soft disable) and records an audit event.",
)
async def deactivate_rider_account(riderId: str, token: accessTokenOut = Depends(verify_admin_token)):
    rider_data = RiderUpdateAccountStatus(accountStatus=AccountStatus.DEACTIVATED)
    update = await update_rider_by_id(user_id=riderId, user_data=rider_data)
    await record_audit_event(
        actor_id=token.get("userId"),
        actor_type="admin",
        action="deactivate_rider",
        target_type="rider",
        target_id=riderId,
        metadata={"reason": "admin_deactivate_request"},
    )
    return APIResponse(status_code=200, data=True, detail="Successfully deactivated rider account")

# --------------------------------------------------
# --------------- RIDE MANAGEMENT ------------------
# --------------------------------------------------


@router.post(
    "/ride/{userId}",
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[RideOut],
    summary="Create ride for user",
    description="Creates a ride on behalf of a rider and computes fare details.",
)
async def create_a_ride_for_user(
    ride_data:RideBase,
    userId:str,
    token: accessTokenOut = Depends(verify_admin_token),
    payment_service: PaymentService = Depends(get_payment_service),
):
    """
    Create a ride on behalf of a rider (admin initiated).

    Access: Admin only (valid admin access token required).
    """
    pick_up = await get_place_details(place_id=ride_data.pickup.place_id)
    drop_off = await get_place_details(place_id=ride_data.destination.place_id)
    if pick_up.data==None or drop_off.data==None:
        raise HTTPException(status_code=500, detail="pickup or dropoff details fetching failed")
    origin = (pick_up.data["lat"],pick_up.data["lng"])
    destination = (drop_off.data["lat"],drop_off.data["lng"])
    stops=None
    if ride_data.stops:
        stops=[]
        index=0
        for stop in ride_data.stops:
            _place_details =await get_place_details(place_id=stop)
            if _place_details.data==None:
                raise HTTPException(status_code=500, detail="pickup or dropoff details fetching failed")
            stops.append((_place_details.data['lat'],_place_details.data['lng']))
    
    map = maps.get_delivery_route(origin=origin,destination=destination,stops=stops)
    
    
    vehicle = Vehicle[ride_data.vehicleType.value]
    price = calculate_fare_using_vehicle_config_and_distance(
        distance=map.totalDistanceMeters,
        time=map.totalDurationSeconds,
        vehicle=vehicle,
    )
    ride_create= RideCreate(
        **ride_data.model_dump(),
        userId=userId,
        price=price,
        origin=Location(latitude=pick_up.data["lat"],longitude=pick_up.data["lng"]),
        map=map,
        paymentStatus=False,
    )
    
    ride  = await add_ride_admin_func(ride_data=ride_create, payment_service=payment_service)
    return APIResponse(data=ride,status_code=200,detail="successfully created ride for user")



@router.get(
    "/ride/{riderId}",
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[List[RideOut]],
    summary="List rides for rider",
    description="Returns rides for a specific rider by rider ID.",
)
async def get_rides_for_a_particular_rider(
    riderId:str 
):
    """
    List rides for a rider by rider ID (admin only).

    Access: Admin only (valid admin access token required).
    """
 
    rides = await retrieve_rides_by_user_id(user_id=riderId)
    return APIResponse(data = rides, status_code=200, detail = f"Successfully retrieved Ride history for rider")


@router.get(
    "/ride/{driverId}",
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[List[RideOut]],
    summary="List rides for driver",
    description="Returns rides for a specific driver by driver ID.",
)
async def get_rides_for_a_particular_driver(
    driverId:str 
):
    """
    List rides for a driver by driver ID (admin only).

    Access: Admin only (valid admin access token required).
    """
 
    rides = await retrieve_rides_by_driver_id(driver_id=driverId)
    return APIResponse(status_code=200,data= rides, detail="Successfully Retrieved Ride history for driver")


@router.patch(
    "/ride/{rideId}",
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[RideOut],
    summary="Cancel ride (admin)",
    description="Cancels a ride by ride ID.",
)
async def cancel_a_ride(
  
    rideId:str,
 
):
    """
    Cancel a ride by ID (admin only).

    Access: Admin only (valid admin access token required).
    """
     
    canceled_ride = RideUpdate(rideStatus=RideStatus.canceled)
    updated_ride = await update_ride_by_id_admin_func(ride_id=rideId,ride_data=canceled_ride)
    return APIResponse(data =updated_ride ,status_code=200,detail="Successfully cancelled ride")



# --------------------------------------------------
# --------------- INVOICE MANAGEMENT ---------------
# --------------------------------------------------

@router.post(
    "/invoice/{rideId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[InvoiceData],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Generate invoice",
    description="Generates and attaches an invoice to a ride.",
)
async def generate_an_invoice_for_a_ride_for_mainly_business_clients(rideId:str,token:accessTokenOut = Depends(verify_admin_token),payment_service: PaymentService = Depends(get_payment_service)):
    """
    Generate and attach an invoice to a ride (admin only).

    Access: Admin only (valid admin access token required).
    """

    invoice_data = await payment_service.send_invoice(ride_id=rideId)
    invoice = InvoiceData(**invoice_data)
    rideUpdate = RideUpdate(invoiceData=invoice)
    ride = await retrieve_ride_by_ride_id(id=rideId)
    await update_ride_by_id_admin_func(ride_id=ride.userId,ride_data=rideUpdate)
    
    return APIResponse(data=invoice_data,status_code=200,detail="Successfully generated invoice")  
   


@router.get(
    "/invoice/{rideId}",
    response_model_exclude={"data": {"password"}},
    response_model=APIResponse[InvoiceData],
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    response_model_exclude_none=True,
    summary="Get invoice",
    description="Returns invoice data for a ride if available.",
)
async def get_an_update_on_the_invoice_for_the_ride(rideId:str,token:accessTokenOut = Depends(verify_admin_token)):
    """
    Retrieve invoice data for a ride if available.

    Access: Admin only (valid admin access token required).
    """
    ride =  await retrieve_ride_by_ride_id(id=rideId) 
    
    if ride.invoiceData:
        return APIResponse(data =ride.invoiceData,status_code=200,detail="Successfully retrieved Invoice data for this ride" )
    else:
        HTTPException(status_code=404,detail="This ride doesn't have an invoice probably not initiated by the admin")

 
 
 
 
 
 
 # -----------------------------------
# ------- PASSWORD MANAGEMENT ------- 
# -----------------------------------

  

@router.patch(
    "/password-reset",
    dependencies=[Depends(verify_admin_token), Depends(log_what_admin_does), Depends(check_admin_account_status_and_permissions)],
    summary="Change admin password",
    description="Updates the authenticated admin password.",
)
async def update_admin_password_while_logged_in(rider_details:AdminUpdatePassword,token:accessTokenOut = Depends(verify_admin_token)):
    """
    Change the authenticated admin password.

    Access: Admin only (valid admin access token required).
    """
    driver =  await update_admin_by_id(driver_id=token.get('userId'),rider_details=rider_details,is_password_getting_changed=True)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")



@router.post(
    "/password-reset/request",
    response_model=APIResponse[ResetPasswordInitiationResponse],
    summary="Request admin password reset",
    description="Initiates the admin password reset flow by sending an OTP.",
)
async def start_password_reset_process_for_rider_that_forgot_password(admin_details:ResetPasswordInitiation):
    """
    Start the admin password reset flow (send OTP).

    Access: Public (no auth).
    """
    driver =  await admin_reset_password_initiation(admin_details=admin_details)   
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")



@router.patch(
    "/password-reset/confirm",
    summary="Confirm admin password reset",
    description="Completes admin password reset with OTP and new password.",
)
async def finish_password_reset_process_for_rider_that_forgot_password(admin_details:ResetPasswordConclusion):
    """
    Complete the admin password reset using an OTP or token.

    Access: Public (no auth).
    """
    
    driver =  await admin_reset_password_conclusion(admin_details=admin_details)
    return APIResponse(data = driver,status_code=200,detail="Successfully updated profile")
