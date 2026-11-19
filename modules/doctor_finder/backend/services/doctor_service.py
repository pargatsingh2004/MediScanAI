"""Verified-directory doctor search and ranking."""

import math

from backend.core.healthcare_intelligence.backend.services.doctor_recommender import DoctorRecommender


def get_recommendations(specialty_codes=None, latitude=None, longitude=None, findings=None, limit=10):
    """Return verified doctors ranked for report specialties and optional location."""
    if (latitude is None) != (longitude is None):
        raise ValueError("Latitude and longitude must be supplied together.")
    if latitude is not None:
        try:
            latitude, longitude = float(latitude), float(longitude)
        except (TypeError, ValueError) as exc:
            raise ValueError("Coordinates must be numbers.") from exc
        if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("Coordinates are outside the valid range.")
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("The result limit must be a whole number.") from exc
    return DoctorRecommender.recommend_doctors(
        specialty_codes=specialty_codes or [],
        user_latitude=latitude,
        user_longitude=longitude,
        report_findings=findings,
        max_results=limit,
    )
