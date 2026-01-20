
from pymongo import ReturnDocument
from core.database import db
from fastapi import HTTPException,status
from typing import List,Optional
from schemas.admin_schema import AdminUpdate, AdminCreate, AdminOut
import os
from dotenv import load_dotenv
from security.hash import hash_password


load_dotenv()
SUPER_ADMIN_EMAIL=os.getenv("SUPER_ADMIN_EMAIL") 
SUPER_ADMIN_PASSWORD=os.getenv("SUPER_ADMIN_PASSWORD")
SUPER_ADMIN_HASHED_PASSWORD=hash_password(SUPER_ADMIN_PASSWORD)


async def create_admin(admin_data: AdminCreate) -> AdminOut:
    admin_dict = admin_data.model_dump(mode='json')
    result =await db.admins.insert_one(admin_dict)
    result = await db.admins.find_one(filter={"_id":result.inserted_id})
  
    returnable_result = AdminOut(**result)
    return returnable_result

async def get_admin(filter_dict: dict) -> Optional[AdminOut]:
    if not filter_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin filter is required."
        )
    try:
        result = await db.admins.find_one(filter_dict)

        if result is None:
            try:
                filter_email = filter_dict.get("email",None)
                filter_id = filter_dict.get("_id",None)
                print(filter_id)
                if filter_email==SUPER_ADMIN_EMAIL or str(filter_id)=="656f7ac12b9d4f6c9e2b9f7d" :
                    return AdminOut(full_name="Super Admin",email=SUPER_ADMIN_EMAIL,password=SUPER_ADMIN_HASHED_PASSWORD,_id="656f7ac12b9d4f6c9e2b9f7d")
            except Exception as e:
                print(e)
                return None 
            return None

        return AdminOut(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching admin: {str(e)}"
        )
    
async def get_admins(filter_dict: Optional[dict] = None,start=0,stop=100) -> List[AdminOut]:
    try:
        filter_dict = filter_dict or {}
        start = max(0, start or 0)
        if stop is None:
            stop = start + 100
        limit = max(0, stop - start)

        cursor = (db.admins.find(filter_dict)
        .skip(start)
        .limit(limit)
        )
        admin_list = []

        async for doc in cursor:
            adminObj =AdminOut(**doc)
            adminObj.password=None
            admin_list.append(adminObj)
        super_admin= AdminOut(_id="656f7ac12b9d4f6c9e2b9f7d",full_name="Super Admin",email=SUPER_ADMIN_EMAIL,password=SUPER_ADMIN_HASHED_PASSWORD)
        super_admin.password=None
        admin_list.append(super_admin)
        return admin_list

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching admins: {str(e)}"
        )
async def update_admin(filter_dict: dict, admin_data: AdminUpdate) -> AdminOut:
    if not filter_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin filter is required."
        )
    update_doc = admin_data.model_dump(exclude_none=True)
    if not update_doc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No admin fields to update."
        )
    result = await db.admins.find_one_and_update(
        filter_dict,
        {"$set": update_doc},
        return_document=ReturnDocument.AFTER
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found."
        )
    returnable_result = AdminOut(**result)
    return returnable_result

async def delete_admin(filter_dict: dict):
    if not filter_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin filter is required."
        )
    result = await db.admins.delete_one(filter_dict)
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin not found."
        )
    return result
