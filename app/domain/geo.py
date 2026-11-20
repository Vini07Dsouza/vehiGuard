"""Distances between cameras and stations (architecture §8.3-8.4)."""

from collections.abc import Iterable
from math import asin, cos, radians, sin, sqrt
from typing import TypeVar

EARTH_RADIUS_KM = 6371.0088
T = TypeVar("T")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance in km between two points on the Earth."""
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def nearest(lat: float, lon: float, places: Iterable[T]) -> tuple[T, float]:
    """The place (with .lat and .lon) closest to the point, and its distance."""
    best, best_km = None, float("inf")
    for place in places:
        km = haversine_km(lat, lon, place.lat, place.lon)
        if km < best_km:
            best, best_km = place, km
    if best is None:
        raise ValueError("No places to choose from")
    return best, best_km
