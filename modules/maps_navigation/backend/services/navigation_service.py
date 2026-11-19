"""Route calculation and navigation URLs."""

import math

from backend.core.healthcare_intelligence.backend.services.directions_service import DirectionsService

VALID_MODES = {"driving", "walking", "transit"}


def _coordinate(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number.")
    if not -90 <= result <= 90 and "latitude" in label.lower():
        raise ValueError(f"{label} is outside the valid range.")
    if "longitude" in label.lower() and not -180 <= result <= 180:
        raise ValueError(f"{label} is outside the valid range.")
    return result


def calculate_route(origin_latitude, origin_longitude, destination_latitude, destination_longitude, travel_mode="driving"):
    """Return distance, duration, and a navigation URL for validated coordinates."""
    mode = str(travel_mode or "driving").lower()
    if mode not in VALID_MODES:
        mode = "driving"
    return DirectionsService.calculate_route_summary(
        _coordinate(origin_latitude, "origin latitude"),
        _coordinate(origin_longitude, "origin longitude"),
        _coordinate(destination_latitude, "destination latitude"),
        _coordinate(destination_longitude, "destination longitude"),
        travel_mode=mode,
    )


def navigation_url(destination_latitude, destination_longitude, origin_latitude=None, origin_longitude=None, travel_mode="driving"):
    """Build a Google Maps URL; origin coordinates must be supplied together."""
    dest_lat = _coordinate(destination_latitude, "destination latitude")
    dest_lng = _coordinate(destination_longitude, "destination longitude")
    if (origin_latitude is None) != (origin_longitude is None):
        raise ValueError("Origin latitude and longitude must be supplied together.")
    origin_lat = _coordinate(origin_latitude, "origin latitude") if origin_latitude is not None else None
    origin_lng = _coordinate(origin_longitude, "origin longitude") if origin_longitude is not None else None
    mode = str(travel_mode or "driving").lower()
    if mode not in VALID_MODES:
        mode = "driving"
    return DirectionsService.get_navigation_url(dest_lat, dest_lng, origin_lat, origin_lng, mode)
