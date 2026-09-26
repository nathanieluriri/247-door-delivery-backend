from typing import List, TypeVar

from core.database import db
from schemas.imports import RideStatus

Account = TypeVar("Account")


async def attach_account_stats(accounts: List[Account], ride_field: str) -> List[Account]:
    """Adds each account's average rating received, rating count and completed trips,
    in two queries for the whole page. ride_field is driverId for drivers, userId for riders."""
    ids = [account.id for account in accounts if getattr(account, "id", None)]
    if not ids:
        return accounts

    ratings = {
        row["_id"]: row
        async for row in db.ratings.aggregate([
            {"$match": {"userId": {"$in": ids}}},
            {"$group": {"_id": "$userId", "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
        ])
    }
    completed = {
        row["_id"]: row["count"]
        async for row in db.rides.aggregate([
            {"$match": {ride_field: {"$in": ids}, "rideStatus": RideStatus.completed.value}},
            {"$group": {"_id": f"${ride_field}", "count": {"$sum": 1}}},
        ])
    }
    for account in accounts:
        summary = ratings.get(account.id)
        account.rating = round(summary["avg"], 2) if summary else None
        account.ratingCount = summary["count"] if summary else 0
        account.completedRides = completed.get(account.id, 0)
    return accounts
