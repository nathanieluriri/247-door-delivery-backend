# ============================================================================
# PAYMENT SERVICE
# ============================================================================
# This file was auto-generated on: 2025-12-15 02:46:53 WAT
# It contains  asynchrounous functions that make use of the repo functions 
# 
# ============================================================================

from bson import ObjectId
from fastapi import HTTPException
from typing import List

from repositories.payment import (
    create_payment,
    get_payment,
    get_payments,
    update_payment,
    delete_payment,
)
from schemas.payment import PaymentCreate, PaymentUpdate, PaymentOut


async def add_payment(payment_data: PaymentCreate) -> PaymentOut:
    """adds an entry of PaymentCreate to the database and returns an object

    Returns:
        _type_: PaymentOut
    """
    return await create_payment(payment_data)


async def remove_payment(payment_id: str):
    """deletes a field from the database and removes PaymentCreateobject 

    Raises:
        HTTPException 400: Invalid payment ID format
        HTTPException 404:  Payment not found
    """
    if not ObjectId.is_valid(payment_id):
        raise HTTPException(status_code=400, detail="Invalid payment ID format")

    filter_dict = {"_id": ObjectId(payment_id)}
    result = await delete_payment(filter_dict)

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Payment not found")

    else: return True
    
async def retrieve_payment_by_payment_id(id: str) -> PaymentOut:
    """Retrieves payment object based specific Id 

    Raises:
        HTTPException 404(not found): if  Payment not found in the db
        HTTPException 400(bad request): if  Invalid payment ID format

    Returns:
        _type_: PaymentOut
    """
    if not ObjectId.is_valid(id):
        raise HTTPException(status_code=400, detail="Invalid payment ID format")

    filter_dict = {"_id": ObjectId(id)}
    result = await get_payment(filter_dict)

    if not result:
        raise HTTPException(status_code=404, detail="Payment not found")

    return result


async def retrieve_payments(start=0,stop=100) -> List[PaymentOut]:
    """Retrieves PaymentOut Objects in a list

    Returns:
        _type_: PaymentOut
    """
    return await get_payments(start=start,stop=stop)


async def update_payment_by_id(payment_id: str, payment_data: PaymentUpdate) -> PaymentOut:
    """updates an entry of payment in the database

    Raises:
        HTTPException 404(not found): if Payment not found or update failed
        HTTPException 400(not found): Invalid payment ID format

    Returns:
        _type_: PaymentOut
    """
    if not ObjectId.is_valid(payment_id):
        raise HTTPException(status_code=400, detail="Invalid payment ID format")

    filter_dict = {"_id": ObjectId(payment_id)}
    result = await update_payment(filter_dict, payment_data)

    if not result:
        raise HTTPException(status_code=404, detail="Payment not found or update failed")

    return result