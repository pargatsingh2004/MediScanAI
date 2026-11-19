"""Unit-aware numeric comparison primitives."""

import math


def calculate_change(first_value, last_value, units=()):
    """Return comparable deltas, or mark them unavailable when units differ."""
    units = {str(unit).strip() for unit in units if str(unit).strip()}
    if len(units) > 1:
        return {"direction": "unit_mismatch", "delta": None, "delta_percent": None}
    first_value, last_value = float(first_value), float(last_value)
    if not math.isfinite(first_value) or not math.isfinite(last_value):
        raise ValueError("Comparison values must be finite numbers.")
    delta = last_value - first_value
    return {
        "direction": "stable" if delta == 0 else "up" if delta > 0 else "down",
        "delta": delta,
        "delta_percent": (delta / abs(first_value) * 100) if first_value else None,
    }
