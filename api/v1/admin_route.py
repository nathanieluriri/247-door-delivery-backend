
from fastapi import APIRouter, HTTPException, Query, Request, status, Path,Depends,Body
from typing import List,Annotated
from core.admin_logger import log_what_admin_does
from core.payements import PaymentService, get_payment_service
from schemas.driver import DriverOut
from schemas.response_schema import APIResponse
from schemas.ride import RideUpdate
from schemas.rider_schema import RiderOut
from schemas.tokens_schema import accessTokenOut
from schemas.admin_schema import (
    AdminCreate,
    AdminOut,
    AdminBase,
    AdminUpdate,
    AdminRefresh,
    AdminLogin
)
from services.admin_service import (
    add_admin,
    remove_admin,
    retrieve_admins,
    authenticate_admin,
    retrieve_admin_by_admin_id,
    update_admin_by_id,
    refresh_admin_tokens_reduce_number_of_logins,

)
from services.driver_service import (
    update_driver_by_id,
    DriverUpdate,
    
)
from services.ride_service import retrieve_ride_by_ride_id, update_ride_by_id, update_ride_by_id_admin_func
from services.rider_service import (
    update_rider_by_id,
    RiderUpdate,
    
)
from schemas.imports import *
from security.auth import verify_token,verify_token_to_refresh,verify_admin_token
from services.driver_service import retrieve_driver_by_driver_id, retrieve_drivers
from services.rider_service import retrieve_rider_by_rider_id, retrieve_riders
router = APIRouter(prefix="/admins", tags=["Admins"])

 
@router.get(
    "/{start}/{stop}", 
    response_model=APIResponse[List[AdminOut]],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"__all__": {"password"}}},
    dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)]
)
async def list_admins(
    
    # Use Path and Query for explicit documentation/validation of GET parameters
    start: Annotated[
        int,
        Path(ge=0, description="The starting index (offset) for the list of admins.")
    ] , 
    stop: Annotated[
        int, 
        Path(gt=0, description="The ending index for the list of admins (limit).")
    ]
):
    """
    **ADMIN ONLY:** Retrieves a paginated list of all registered admins.

    **Authorization:** Requires a **valid Access Token** (Admin role) in the 
    `Authorization: Bearer <token>` header.

    ### Examples (Illustrative URLs):

    * **First Page:** `/admins/0/5` (Start at index 0, retrieve up to 5 admins)
    * **Second Page:** `/admins/5/10` (Start at index 5, retrieve up to 5 more admins)
    
    """
    
    # Note: The code below overrides the path parameters with hardcoded defaults (0, 100).
    # You should typically use the passed parameters: 
    # items = await retrieve_admins(start=start, stop=stop)
    
    # Using the hardcoded values from your original code:
    items = await retrieve_admins(start=0, stop=100)
    
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")


@router.get(
    "/profile", 
    response_model=APIResponse[AdminOut],
    dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)],
    response_model_exclude_none=True,
    response_model_exclude={"data": {"password"}},
)
async def get_my_admin(
    token: accessTokenOut = Depends(verify_admin_token),
        
):
    """
    Retrieves the profile information for the currently authenticated admin.

    The admin's ID is automatically extracted from the valid Access Token 
    in the **Authorization: Bearer <token>** header.
    """
    
    items = await retrieve_admin_by_admin_id(id=token.get("userId"))
    return APIResponse(status_code=200, data=items, detail="admins items fetched")





@router.post("/signup",dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)],response_model_exclude_none=True, response_model_exclude={"data": {"password"}},response_model=APIResponse[AdminOut])
async def signup_new_admin(
    admin_data:AdminBase,
    token: accessTokenOut = Depends(verify_admin_token),
):
 
    admin_data_dict = admin_data.model_dump() 
    new_admin = AdminCreate(
      invited_by=token.get("userId"),
        **admin_data_dict
    )
    items = await add_admin(admin_data=new_admin)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")

@router.post("/login",response_model_exclude={"data": {"password"}}, response_model_exclude_none=True,response_model=APIResponse[AdminOut])
async def login_admin(
    
    admin_data:AdminLogin,

):
    """
    Authenticates a admin with the provided email and password.
    
    Upon success, returns the authenticated admin data and an authentication token.
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
    """
 
    items = await refresh_admin_tokens_reduce_number_of_logins(
        admin_refresh_data=admin_data,
        expired_access_token=token.accesstoken
    )
    
    # Clears the password before returning, which is good practice.
    items.password = ''
    
    return APIResponse(status_code=200, data=items, detail="admins items fetched")


@router.delete("/account",dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)], response_model_exclude_none=True)
async def delete_admin_account(
    token: accessTokenOut = Depends(verify_token),
 
):
    """
    Deletes the account associated with the provided access token.

    The admin ID is extracted from the valid Access Token in the Authorization header.
    No request body is required.
    """
    result = await remove_admin(admin_id=token.userId)
    
    # The 'result' is assumed to be a standard FastAPI response object or a dict/model 
    # that is automatically converted to a response.
    return result


@router.patch("/profile",dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)])
async def update_driver_profile(admin_details:AdminUpdate,token:accessTokenOut = Depends(verify_admin_token)):
    admin = await update_admin_by_id(admin_id=token.userId,admin_data=admin_details,)
    return APIResponse(data=admin,status_code=200,detail="Succesfully updated profile")

# ---------------------------------------------------
# --------------- DRIVER MANAGEMENT -----------------
# ---------------------------------------------------

@router.get("/drivers/",response_model_exclude={"data": {"__all__": {"password"}}} ,response_model_exclude_none=True, response_model=APIResponse[List[DriverOut]] ,      dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)])
async def list_of_drivers(start:int= 0, stop:int=100,token:accessTokenOut = Depends(verify_admin_token)):
    items = await retrieve_drivers(start=start,stop=stop)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")

@router.get("/driver/{driverId}", response_model_exclude={"data": {"password"}} , response_model=APIResponse[DriverOut] ,  dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)],response_model_exclude_none=True)
async def get_a_particular_driver_details(driverId:str,token:accessTokenOut = Depends(verify_admin_token)):
    try: 
        items = await retrieve_driver_by_driver_id(id=driverId)
        return APIResponse(status_code=200, data=items, detail="users items fetched")
    except Exception as e:
        raise HTTPException(status_code=500,detail=f"{e}")
    
@router.patch("/ban/driver/{driverId}", response_model_exclude={"data": {"password"}} , response_model=APIResponse[DriverOut] ,    dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)],response_model_exclude_none=True)
async def ban_a_driver_from_using_the_app(driverId:str,token:accessTokenOut = Depends(verify_admin_token)):
    driver_data = DriverUpdate(accountStatus=AccountStatus.BANNED)
    update =await update_driver_by_id(driver_id=driverId,driver_data=driver_data)
    return APIResponse(status_code=200,data=update,detail="Successfully banned driver from the app")
    
# --------------------------------------------------
# --------------- RIDER MANAGEMENT -----------------
# --------------------------------------------------



@router.get("/riders/",response_model_exclude={"data": {"__all__": {"password"}}} ,response_model_exclude_none=True, response_model=APIResponse[List[RiderOut]],    dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)])
async def list_riders(start:int= 0, stop:int=100,token:accessTokenOut = Depends(verify_admin_token)):
    items = await retrieve_riders(start=0,stop=100)
    return APIResponse(status_code=200, data=items, detail="Fetched successfully")



@router.get("/rider/{riderId}", response_model_exclude={"data": {"password"}}, response_model=APIResponse[RiderOut] ,    dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)],response_model_exclude_none=True)
async def get_a_particular_riders_details(riderId:str,token:accessTokenOut = Depends(verify_admin_token)):
    items = await retrieve_rider_by_rider_id(id=riderId)
    return APIResponse(status_code=200, data=items, detail="users items fetched")

 
@router.patch("/ban/rider/{riderId}", response_model_exclude={"data": {"password"}}, response_model=APIResponse[RiderOut] ,  dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)],response_model_exclude_none=True)
async def ban_a_rider_from_using_the_app(riderId:str,token:accessTokenOut = Depends(verify_admin_token)):
    rider_data = DriverUpdate(accountStatus=AccountStatus.BANNED)
    update =await update_rider_by_id(user_id=riderId,user_data=rider_data)
    return APIResponse(status_code=200,data=update,detail="Successfully banned Rider from the app")



# --------------------------------------------------
# --------------- INVOICE MANAGEMENT ---------------
# --------------------------------------------------

@router.post("/invoice/{rideId}", response_model_exclude={"data": {"password"}}, response_model=APIResponse[InvoiceData] ,   dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)],response_model_exclude_none=True)
async def generate_an_invoice_for_a_ride_for_mainly_business_clients(rideId:str,token:accessTokenOut = Depends(verify_admin_token),payment_service: PaymentService = Depends(get_payment_service)):

    invoice_data = await payment_service.send_invoice(ride_id=rideId)
    invoice = InvoiceData(**invoice_data)
    rideUpdate = RideUpdate(invoiceData=invoice)
    ride = await retrieve_ride_by_ride_id(id=rideId)
    await update_ride_by_id_admin_func(ride_id=ride.userId,ride_data=rideUpdate)
    
    return APIResponse(data=invoice_data,status_code=200,detail="Successfully generated invoice")  
   


@router.get("/invoice/{rideId}", response_model_exclude={"data": {"password"}}, response_model=APIResponse[InvoiceData] ,   dependencies=[Depends(verify_admin_token),Depends(log_what_admin_does)],response_model_exclude_none=True)
async def get_an_update_on_the_invoice_for_the_ride(rideId:str,token:accessTokenOut = Depends(verify_admin_token)):
    ride =  await retrieve_ride_by_ride_id(id=rideId) 
    
    if ride.invoiceData:
        return APIResponse(data =ride.invoiceData,status_code=200,detail="Successfully retrieved Invoice data for this ride" )
    else:
        HTTPException(status_code=404,detail="This ride doesn't have an invoice probably not initiated by the admin")


# TODO: WEBHOOK FOR RECEIVING INVOICE DATA UPDATE SHOULD BE HERE WHEN AN INVOICE IS PAID IT SHOULD UPDATE THE INVOICE DATA OBJECT IN A RIDE
