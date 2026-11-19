"""Numeric utilities for report trend summaries."""

import math


def compare_last_values(values):
    """Summarize the last two numeric values without dividing by zero."""
    values = [float(value) for value in values if value is not None]
    values = [value for value in values if math.isfinite(value)]
    if not values:
        return {"latest": None, "previous": None, "delta": None, "delta_percent": None, "direction": "unknown"}
    latest = values[-1]
    previous = values[-2] if len(values) > 1 else None
    delta = latest - previous if previous is not None else None
    return {
        "latest": latest,
        "previous": previous,
        "delta": delta,
        "delta_percent": (delta / abs(previous) * 100) if previous else None,
        "direction": "stable" if delta == 0 else "up" if delta is not None and delta > 0 else "down" if delta is not None else "unknown",
    }
