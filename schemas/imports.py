from bson import ObjectId
from pydantic import AliasChoices, GetJsonSchemaHandler
from pydantic import BaseModel, EmailStr, Field,model_validator
from pydantic_core import core_schema
from datetime import datetime,timezone
from typing import Optional,List,Any
from enum import Enum
import time

class RideStatus(str, Enum):
    arrivingToPickup="arrivingToPickup"
    drivingToDestination="drivingToDestination"
    canceled = "canceled"
    pendingPayment="pendingPayment"
    findingDriver="findingDriver"
    completed="completed"
    
    
class AccountStatus(str, Enum):
    ACTIVE="active"
    PENDING_VERIFICATION="pendingVerification"
    SUSPENDED = "suspended"
    BANNED="banned"
    DEACTIVATED="deactivated"
    
ALLOWED_ACCOUNT_STATUS_TRANSITIONS: dict[AccountStatus, set[AccountStatus]] = {
    AccountStatus.PENDING_VERIFICATION: {
        AccountStatus.ACTIVE,
        AccountStatus.BANNED,
        AccountStatus.SUSPENDED,
    },
    AccountStatus.ACTIVE: {
        AccountStatus.SUSPENDED,
        AccountStatus.BANNED,
        AccountStatus.DEACTIVATED,
    },
    AccountStatus.SUSPENDED: {
        AccountStatus.ACTIVE,
        AccountStatus.BANNED,
    },
    AccountStatus.BANNED: set(),  # irreversible (admin decision)
    AccountStatus.DEACTIVATED: {
        AccountStatus.ACTIVE,
    },
}

    
class InvoiceData(BaseModel):
    
    status:Optional[str]=None
    
    email_sent_to: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("email_sent_to", "emailSentTo"),
        serialization_alias="emailSentTo",
    )
    invoice_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("invoice_url", "invoiceUrl"),
        serialization_alias="invoiceUrl",
    )
    invoice_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("invoice_id", "invoiceId"),
        serialization_alias="invoiceId",
    )