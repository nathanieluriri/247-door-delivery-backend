from pydantic import BaseModel, Field
from typing import List, Optional
import googlemaps
from datetime import datetime
from dotenv import load_dotenv
import os
load_dotenv()

GOOGLE_MAP_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
# --- 1. Define Pydantic Models ---



class RouteLeg(BaseModel):
    """Represents a single segment of the journey (e.g., Pickup -> Stop 1)."""
    startAddress: str
    endAddress: str
    distanceMeters: int
    durationSeconds: int

class DeliveryRouteResponse(BaseModel):
    """The complete route summary to return to the Frontend."""
    totalDistanceMeters: int
    totalDurationSeconds: int
    encodedPolyline: str = Field(..., description="The compressed string for drawing the map line")
    waypointOrder: List[int] = Field(default_factory=list, description="Order of stops if optimized")
    legs: List[RouteLeg] = Field(default_factory=list, description="Detailed breakdown of each segment")

# --- 2. The Service Class ---

class MapsService:
    def __init__(self, api_key: str):
        self.client = googlemaps.Client(key=api_key)

    def get_delivery_route(
        self, 
        origin: tuple, 
        destination: tuple, 
        stops: list = None, 
        optimize: bool = False
    ) -> Optional[DeliveryRouteResponse]:
        
        try:
            # Request directions from Google
            directions_result = self.client.directions(
                origin=origin,
                destination=destination,
                waypoints=stops, 
                optimize_waypoints=optimize,
                mode="driving",
                departure_time=datetime.now()
            )

            if not directions_result:
                return None

            route = directions_result[0]
            
            # Variables to calculate totals
            total_distance = 0
            total_duration = 0
            parsed_legs = []

            # Loop through the legs to extract detailed info
            for leg in route.get('legs', []):
                dist_val = leg['distance']['value']
                dur_val = leg['duration']['value']
                
                total_distance += dist_val
                total_duration += dur_val
                
                # Create a Pydantic object for this leg
                parsed_legs.append(
                    RouteLeg(
                        startAddress=leg['start_address'],
                        endAddress=leg['end_address'],
                        distanceMeters=dist_val,
                        durationSeconds=dur_val
                    )
                )

            # Return the main Pydantic object
            return DeliveryRouteResponse(
                totalDistanceMeters=total_distance,
                totalDurationSeconds=total_duration,
                encodedPolyline=route['overview_polyline']['points'],
                waypointOrder=route.get('waypoint_order', []),
                legs=parsed_legs
            )

        except Exception as e:
    
            return None


 
maps = MapsService(GOOGLE_MAP_API_KEY)