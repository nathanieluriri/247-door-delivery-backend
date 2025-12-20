from pydantic import BaseModel
from typing import Union
from redis_om import HashModel, Field
from redis_om.connections import get_redis_connection
from core.redis_cache import cache_db
import time
from schemas.place import Location
class SmallUserObject(BaseModel):
    user_type:str
    user_id:str   
    

    


# class UserLocation(HashModel):
#     """
#     Stores real-time user location for proximity queries.
#     """

#     sid: str = Field(index=True, primary_key=True)
#     user_id: str = Field(index=True)
#     location: GeoPoint = Field(index=True)
#     last_updated: int = Field(default_factory=lambda: int(time.time()), index=True)
#     role: str = Field(index=True, default="rider")

#     class Meta:
#         database = cache_db
#         global_key_prefix = "live"
#         expire = 360   # <--- TTL in seconds (example: 6 minutes)
