# ============================================================================
#PAYOUT SCHEMA 
# ============================================================================
# This file was auto-generated on: 2025-12-21 02:16:17 WAT
# It contains Pydantic classes  database
# for managing attributes and validation of data in and out of the MongoDB database.
#
# ============================================================================

from schemas.imports import *
from pydantic import Field
import time

# Base model to represent payout records
class PayoutBase(BaseModel):
    payoutOption: PayoutOptions  # Type of payout (earnings, withdrawable, or withdrawal)
    amount: float  # Amount for the payout
    rideIds: Optional[List[str]] = Field(default_factory=list)  # List of ride IDs (only for earnings payouts)
    driverId: str  # User ID (driver or rider)
    
    # Method to calculate total earnings (if needed for reporting)
    def calculate_total_amount(self) -> float:
        return self.amount  # In case there's additional logic for calculating totals
    
    # Method to track ride completion and earnings
    def add_ride(self, ride_id: str):
        if self.payoutOption == PayoutOptions.totalEarnings:
            if self.rideIds is None:
                self.rideIds = []
            self.rideIds.append(ride_id)

# Payout creation model (when a payout record is created after a ride or withdrawal)
class PayoutCreate(PayoutBase):
    date_created: int = Field(default_factory=lambda: int(time.time()))  # Automatically set the creation timestamp
    last_updated: int = Field(default_factory=lambda: int(time.time()))  # Automatically set the last updated timestamp

    def add_ride_to_earnings(self, ride_id: str):
        # Add completed ride to earnings list and update total earnings
        if self.payoutOption == PayoutOptions.totalEarnings:
            self.add_ride(ride_id)
            self.last_updated = int(time.time())  # Update the timestamp

    def update_balance_after_withdrawal(self, withdrawal_amount: float):
        # Logic for updating withdrawable balance after a withdrawal
        if self.payoutOption == PayoutOptions.withdrawalHistory:
            self.amount -= withdrawal_amount
            self.last_updated = int(time.time())  # Update timestamp after withdrawal

# Payout update model (when we update existing payouts)
class PayoutUpdate(BaseModel):
    payoutOption: Optional[PayoutOptions] = None  # Update the payout option type if needed
    amount: Optional[float] = None  # Update the amount (e.g., after a withdrawal)
    rideIds: Optional[List[str]] = None  # Optionally update the ride IDs (only for totalEarnings)
    last_updated: int = Field(default_factory=lambda: int(time.time()))  # Update the timestamp

class PayoutBalanceOut(BaseModel):
    currency: str
    available_balance: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("available_balance", "availableBalance"),
        serialization_alias="availableBalance",
    )
    total_withdrawn: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("total_withdrawn", "totalWithdrawn"),
        serialization_alias="totalWithdrawn",
    )
    total_earnings: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("total_earnings", "totalEarnings"),
        serialization_alias="totalEarnings",
    )

class PayoutRequestIn(BaseModel):
    amount: int = Field(..., description="Amount to payout in smallest currency unit (e.g., pence for GBP)", gt=0)
    description: Optional[str] = Field(None, description="Description for the payout")
    instant: bool = Field(False, description="Whether to request an instant payout (higher fees)")

class PayoutOut(PayoutBase):
    # Add other fields here 
    id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("_id", "id"),
        serialization_alias="id",
    )
    date_created: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("date_created", "dateCreated"),
        serialization_alias="dateCreated",
    )
    last_updated: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("last_updated", "lastUpdated"),
        serialization_alias="lastUpdated",
    )
    
    @model_validator(mode="before")
    @classmethod
    def convert_objectid(cls, values):
        if "_id" in values and isinstance(values["_id"], ObjectId):
            values["_id"] = str(values["_id"])  # coerce to string before validation
        return values
            
    class Config:
        populate_by_name = True  # allows using `id` when constructing the model
        arbitrary_types_allowed = True  # allows ObjectId type
        json_encoders ={
            ObjectId: str  # automatically converts ObjectId → str
        }
