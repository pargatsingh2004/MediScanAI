"""Nearby hospital discovery through the verified directory and configured Places API."""

import math

from backend.core.healthcare_intelligence.backend.services.hospital_finder import (
    HospitalFinder,
    haversine_distance,
)


def _coordinate(value, minimum, maximum, label):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if not math.isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{label} is outside the valid range.")
    return result


def search_nearby_hospitals(latitude, longitude, radius_meters=10000, specialty_code=None, hospital_type=None, sort_by="distance"):
    """Search within a bounded radius and return normalized hospital records."""
    try:
        radius_meters = max(100, min(int(radius_meters), 50000))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Search radius must be a whole number of meters.") from exc
    return HospitalFinder.search_nearby_hospitals(
        _coordinate(latitude, -90, 90, "Latitude"),
        _coordinate(longitude, -180, 180, "Longitude"),
        radius_meters=radius_meters,
        specialty_code=specialty_code,
        hospital_type=hospital_type,
        sort_by=sort_by if sort_by in {"distance", "rating"} else "distance",
    )


__all__ = ["search_nearby_hospitals", "haversine_distance"]
