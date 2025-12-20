from redis_om import HashModel,Field
from typing import Optional
from core.redis_cache import cache_db
from web_socket_handler.schemas.imports import Location

class ActiveRiders(HashModel):
    sid: str = Field(index=True)
    user_id: str = Field(index=True)
    coordinates:Optional[Location]=None
    

    class Meta:
        database = cache_db
  