import math
import logging
import requests
from typing import List, Dict, Any, Optional
from django.conf import settings

logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    R = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


class HospitalFinder:
    """Finds, filters, and ranks nearby hospitals using Google Places API and verified directory."""

    @classmethod
    def search_nearby_hospitals(
        cls,
        latitude: float,
        longitude: float,
        radius_meters: int = 10000,
        specialty_code: Optional[str] = None,
        hospital_type: Optional[str] = None,
        sort_by: str = "distance",  # 'distance' | 'rating'
    ) -> List[Dict[str, Any]]:
        """Search nearby hospitals using Google Places API with verified database fallback."""
        places_api_key = getattr(settings, "GOOGLE_PLACES_API_KEY", "") or getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        hospitals_list = []

        # 1. Try Google Places API (Nearby Search) if key is provided
        if places_api_key and places_api_key != "your-google-places-api-key":
            try:
                url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                params = {
                    "location": f"{latitude},{longitude}",
                    "radius": radius_meters,
                    "type": "hospital",
                    "key": places_api_key,
                }
                response = requests.get(url, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    for place in results:
                        place_lat = place["geometry"]["location"]["lat"]
                        place_lng = place["geometry"]["location"]["lng"]
                        dist = haversine_distance(latitude, longitude, place_lat, place_lng)
                        hospitals_list.append({
                            "id": None,
                            "place_id": place.get("place_id"),
                            "name": place.get("name"),
                            "address": place.get("vicinity", "Address available via Google Maps"),
                            "latitude": place_lat,
                            "longitude": place_lng,
                            "rating": place.get("rating", 0.0),
                            "reviews_count": place.get("user_ratings_total", 0),
                            "distance_km": dist,
                            "hospital_type": "Google Places",
                            "phone": "",
                            "website": "",
                            "emergency_services": False,
                            "verified": False,
                            "source": "google_places",
                        })
            except Exception as e:
                logger.warning(f"Google Places API request failed: {e}")

        # 2. Query Verified Database Directory
        from backend.core.healthcare_intelligence.backend.models import Hospital

        db_qs = Hospital.objects.filter(verified=True)
        if hospital_type:
            db_qs = db_qs.filter(hospital_type__iexact=hospital_type)
        if specialty_code:
            db_qs = db_qs.filter(specialties__code__iexact=specialty_code)

        for h in db_qs:
            dist = haversine_distance(latitude, longitude, h.latitude, h.longitude)
            # Check if within radius (meters to km)
            if dist <= (radius_meters / 1000.0):
                hospitals_list.append({
                    "id": h.id,
                    "place_id": h.place_id,
                    "name": h.name,
                    "address": h.address,
                    "latitude": h.latitude,
                    "longitude": h.longitude,
                    "rating": h.rating,
                    "reviews_count": h.reviews_count,
                    "distance_km": dist,
                    "hospital_type": h.hospital_type,
                    "phone": h.phone,
                    "website": h.website,
                    "emergency_services": h.emergency_services,
                    "verified": h.verified,
                    "source": "verified_database",
                })

        # Deduplicate by place_id or name
        seen = set()
        unique_hospitals = []
        for item in hospitals_list:
            key = item.get("place_id") or item["name"].lower()
            if key not in seen:
                seen.add(key)
                unique_hospitals.append(item)

        # Sort
        if sort_by == "rating":
            unique_hospitals.sort(key=lambda x: (x["rating"], -x["distance_km"]), reverse=True)
        else:
            unique_hospitals.sort(key=lambda x: x["distance_km"])

        return unique_hospitals
