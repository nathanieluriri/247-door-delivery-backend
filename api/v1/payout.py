
from fastapi import APIRouter, HTTPException, Query, Path, status
from typing import List, Optional
import json
from schemas.response_schema import APIResponse
from schemas.payout import (
    PayoutCreate,
    PayoutOut,
    PayoutBase,
    PayoutUpdate,
)
from services.payout_service import (
    add_payout,
    remove_payout,
    retrieve_payouts,
    retrieve_payout_by_payout_id,
    update_payout_by_id,
)

router = APIRouter(prefix="/payouts", tags=["Payouts"])


# ------------------------------
# List Payouts (with pagination and filtering)
# ------------------------------
@router.get("/", response_model=APIResponse[List[PayoutOut]])
async def list_payouts(
    start: Optional[int] = Query(None, description="Start index for range-based pagination"),
    stop: Optional[int] = Query(None, description="Stop index for range-based pagination"),
    page_number: Optional[int] = Query(None, description="Page number for page-based pagination (0-indexed)"),
    # New: Filter parameter expects a JSON string
    filters: Optional[str] = Query(None, description="Optional JSON string of MongoDB filter criteria (e.g., '{\"field\": \"value\"}')")
):
    """
    Retrieves a list of Payouts with pagination and optional filtering.
    - Priority 1: Range-based (start/stop)
    - Priority 2: Page-based (page_number)
    - Priority 3: Default (first 100)
    """
    PAGE_SIZE = 50
    parsed_filters = {}

    # 1. Handle Filters
    if filters:
        try:
            parsed_filters = json.loads(filters)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON format for 'filters' query parameter."
            )

    # 2. Determine Pagination
    # Case 1: Prefer start/stop if provided
    if start is not None or stop is not None:
        if start is None or stop is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both 'start' and 'stop' must be provided together.")
        if stop < start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'stop' cannot be less than 'start'.")
        
        # Pass filters to the service layer
        items = await retrieve_payouts(filters=parsed_filters, start=start, stop=stop)
        return APIResponse(status_code=200, data=items, detail="Fetched successfully")

    # Case 2: Use page_number if provided
    elif page_number is not None:
        if page_number < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'page_number' cannot be negative.")
        
        start_index = page_number * PAGE_SIZE
        stop_index = start_index + PAGE_SIZE
        # Pass filters to the service layer
        items = await retrieve_payouts(filters=parsed_filters, start=start_index, stop=stop_index)
        return APIResponse(status_code=200, data=items, detail=f"Fetched page {page_number} successfully")

    # Case 3: Default (no params)
    else:
        # Pass filters to the service layer
        items = await retrieve_payouts(filters=parsed_filters, start=0, stop=100)
        detail_msg = "Fetched first 100 records successfully"
        if parsed_filters:
            # If filters were applied, adjust the detail message
            detail_msg = f"Fetched first 100 records successfully (with filters applied)"
        return APIResponse(status_code=200, data=items, detail=detail_msg)


# ------------------------------
# Retrieve a single Payout
# ------------------------------
@router.get("/{id}", response_model=APIResponse[PayoutOut])
async def get_payout_by_id(
    id: str = Path(..., description="payout ID to fetch specific item")
):
    """
    Retrieves a single Payout by its ID.
    """
    item = await retrieve_payout_by_payout_id(id=id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payout not found")
    return APIResponse(status_code=200, data=item, detail="payout item fetched")


# ------------------------------
# Create a new Payout
# ------------------------------
# Uses PayoutBase for input (correctly)
@router.post("/", response_model=APIResponse[PayoutOut], status_code=status.HTTP_201_CREATED)
async def create_payout(payload: PayoutBase):
    """
    Creates a new Payout.
    """
    # Creates PayoutCreate object which includes date_created/last_updated
    new_data = PayoutCreate(**payload.model_dump()) 
    new_item = await add_payout(new_data)
    if not new_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create payout")
    
    return APIResponse(status_code=201, data=new_item, detail=f"Payout created successfully")


# ------------------------------
# Update an existing Payout
# ------------------------------
# Uses PATCH for partial update (correctly)
@router.patch("/{id}", response_model=APIResponse[PayoutOut])
async def update_payout(
    id: str = Path(..., description="ID of the {db_name} to update"),
    payload: PayoutUpdate = None
):
    """
    Updates an existing Payout by its ID.
    Assumes the service layer handles partial updates (e.g., ignores None fields in payload).
    """
    updated_item = await update_payout_by_id(id=id, data=payload)
    if not updated_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payout not found or update failed")
    
    return APIResponse(status_code=200, data=updated_item, detail=f"Payout updated successfully")


# ------------------------------
# Delete an existing Payout
# ------------------------------
@router.delete("/{id}", response_model=APIResponse[None])
async def delete_payout(id: str = Path(..., description="ID of the payout to delete")):
    """
    Deletes an existing Payout by its ID.
    """
    deleted = await remove_payout(id)
    if not deleted:
        # This assumes remove_payout returns a boolean or similar
        # to indicate if deletion was successful (i.e., item was found).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Payout not found or deletion failed")
    
    return APIResponse(status_code=200, data=None, detail=f"Payout deleted successfully")
