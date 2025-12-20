from redis_om import HashModel, Field
from typing import Optional
from core.redis_cache import cache_db
from web_socket_handler.schemas.imports import Location



    
class ActiveDrivers(HashModel):
    sid: str = Field(index=True)
    user_id: str = Field(index=True)
    coordinates: Optional[str] = None  # Store Location as JSON string
    is_active: Optional[int] = Field(default=0,index=True)     # Store boolean as 0 or 1
 
    class Meta:
        database = cache_db

    # Convenience methods for serialization
    def set_coordinates(self, location: Location):
        self.coordinates = location.model_dump_json()  # Serialize to JSON string

    def get_coordinates(self) -> Optional[Location]:
        if self.coordinates:
            return Location.model_validate_json(self.coordinates)
        return None

    def set_active(self, active: bool):
        self.is_active = 1 if active else 0
 
    
    def is_driver_active(self) -> bool:
        return bool(self.is_active)