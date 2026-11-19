import math
import logging
import requests
from typing import Dict, Any, Optional
from django.conf import settings
from .hospital_finder import haversine_distance

logger = logging.getLogger(__name__)


class DirectionsService:
    """Computes routing details and generates official Google Maps turn-by-turn navigation URLs."""

    @classmethod
    def get_navigation_url(
        cls,
        destination_lat: float,
        destination_lng: float,
        origin_lat: Optional[float] = None,
        origin_lng: Optional[float] = None,
        travel_mode: str = "driving",
    ) -> str:
        """Generates standard Google Maps navigation URL."""
        base_url = "https://www.google.com/maps/dir/?api=1"
        url = f"{base_url}&destination={destination_lat},{destination_lng}&travelmode={travel_mode.lower()}"
        if origin_lat is not None and origin_lng is not None:
            url += f"&origin={origin_lat},{origin_lng}"
        return url

    @classmethod
    def calculate_route_summary(
        cls,
        origin_lat: float,
        origin_lng: float,
        destination_lat: float,
        destination_lng: float,
        travel_mode: str = "driving",
    ) -> Dict[str, Any]:
        """Calculates route distance, estimated travel time, and turn-by-turn navigation link."""
        routes_api_key = (
            getattr(settings, "GOOGLE_ROUTES_API_KEY", "")
            or getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        )

        # 1. Try Google Directions API if key configured
        if routes_api_key and routes_api_key != "your-google-routes-api-key":
            try:
                api_url = "https://maps.googleapis.com/maps/api/directions/json"
                params = {
                    "origin": f"{origin_lat},{origin_lng}",
                    "destination": f"{destination_lat},{destination_lng}",
                    "mode": travel_mode.lower(),
                    "key": routes_api_key,
                }
                res = requests.get(api_url, params=params, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    routes = data.get("routes", [])
                    if routes:
                        leg = routes[0]["legs"][0]
                        nav_url = cls.get_navigation_url(destination_lat, destination_lng, origin_lat, origin_lng, travel_mode)
                        return {
                            "distance_text": leg["distance"]["text"],
                            "distance_meters": leg["distance"]["value"],
                            "duration_text": leg["duration"]["text"],
                            "duration_seconds": leg["duration"]["value"],
                            "navigation_url": nav_url,
                            "travel_mode": travel_mode.upper(),
                            "source": "google_directions_api",
                        }
            except Exception as e:
                logger.warning(f"Google Directions API call failed: {e}")

        # 2. Precise Geodesic Route Estimation Fallback
        dist_km = haversine_distance(origin_lat, origin_lng, destination_lat, destination_lng)
        dist_meters = int(dist_km * 1000)

        # Estimate travel speeds: Driving ~ 30 km/h in city; Walking ~ 4.5 km/h
        mode_lower = travel_mode.lower()
        if mode_lower == "walking":
            speed_kmh = 4.5
        elif mode_lower == "transit":
            speed_kmh = 22.0
        else:
            speed_kmh = 32.0  # Urban driving average

        duration_hours = dist_km / max(1.0, speed_kmh)
        duration_minutes = max(1, int(round(duration_hours * 60)))
        duration_seconds = duration_minutes * 60

        if duration_minutes >= 60:
            hrs = duration_minutes // 60
            mins = duration_minutes % 60
            duration_text = f"{hrs} hr {mins} min" if mins else f"{hrs} hr"
        else:
            duration_text = f"{duration_minutes} min"

        distance_text = f"{dist_km} km" if dist_km >= 1.0 else f"{dist_meters} m"
        nav_url = cls.get_navigation_url(destination_lat, destination_lng, origin_lat, origin_lng, travel_mode)

        return {
            "distance_text": distance_text,
            "distance_meters": dist_meters,
            "duration_text": duration_text,
            "duration_seconds": duration_seconds,
            "navigation_url": nav_url,
            "travel_mode": travel_mode.upper(),
            "source": "geodesic_estimation",
        }
