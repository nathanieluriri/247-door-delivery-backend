from bson import ObjectId
from pydantic import AliasChoices, GetJsonSchemaHandler
from pydantic import BaseModel, EmailStr, Field,model_validator
from pydantic_core import core_schema
from datetime import datetime,timezone
from typing import Dict, Optional,List,Any
from enum import Enum
import time

from security.hash import hash_password

class PayoutOptions(str, Enum):
    totalEarnings = "totalEarnings"  # Total money earned
    withdrawableBalance = "withdrawableBalance"  # Money that can be withdrawn
    withdrawalHistory = "withdrawalHistory"  # Track withdrawal requests
    
class LoginType(str,Enum):
    password="password"
    passwordless="passwordless"
    google="google"
class UserType(str,Enum):
    rider= "rider"
    driver="driver"
    admin="admin"
class ResetPasswordInitiation(BaseModel):
    # Add other fields here
    email:EmailStr 
    
class ResetPasswordInitiationResponse(BaseModel):
    # Add other fields here
    resetToken:str
    
    
class ResetPasswordConclusion(BaseModel):
    # Add other fields here
    otp:str
    resetToken:str 
    password:str 
class Permission(BaseModel):
    name: str
    methods: List[str]
    path: str
    description: Optional[str] = None
    
class PermissionList(BaseModel):
    permissions: list[Permission]


class RideStatus(str, Enum):
    pendingPayment="pendingPayment"
    findingDriver="findingDriver"
    arrivingToPickup="arrivingToPickup"
    drivingToDestination="drivingToDestination"
    canceled = "canceled"
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

class StripeEvent(BaseModel):
    id: str
    type: str
    data: Dict[str, Any]
class CheckoutSessionObject(BaseModel):
    id: str
    payment_status: str
    amount_total: Optional[int]
    currency: Optional[str]
    payment_intent: Optional[str]
    payment_link: Optional[str]
    metadata: Dict[str, str] = Field(default_factory=dict)
    
class InvoiceData(BaseModel):
    id:str
    status:Optional[str]=None
    amount_paid: Optional[int]
    currency: Optional[str]
    customer: Optional[str]
    metadata: Dict[str, str] = Field(default_factory=dict)
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
 
 
 
ALLOWED_RIDE_STATUS_TRANSITIONS: dict[RideStatus, set[RideStatus]] = {
    RideStatus.pendingPayment: {
        RideStatus.findingDriver,
        RideStatus.canceled,
    },
    RideStatus.findingDriver: {
        RideStatus.arrivingToPickup,
        RideStatus.canceled,
    },
    RideStatus.arrivingToPickup: {
        RideStatus.drivingToDestination,
        RideStatus.canceled,
    },
    RideStatus.drivingToDestination: {
        RideStatus.completed,
    },
    RideStatus.canceled: set(),   # terminal
    RideStatus.completed: set(),  # terminal
}


RIDE_REFUND_RULES: dict[tuple[RideStatus, RideStatus], float] = {
    (RideStatus.pendingPayment, RideStatus.canceled): 0.95,
    (RideStatus.findingDriver, RideStatus.canceled): 0.90,
    (RideStatus.arrivingToPickup, RideStatus.canceled): 0.75,
}
