"""Utilitas geometri sederhana (tanpa geopandas)."""

import math

from pyproj import Geod
from shapely.geometry import Polygon

_GEOD = Geod(ellps="WGS84")

BATAM_CENTER = (1.10, 104.03)  # (lat, lon)


def area_m2(geom) -> float:
    """Luas geodesik geometri lon/lat dalam m²."""
    return abs(_GEOD.geometry_area_perimeter(geom)[0])


def square_around(lon: float, lat: float, area: float) -> Polygon:
    """Buat persegi berpusat di (lon, lat) dengan luas `area` m²."""
    half = math.sqrt(area) / 2
    dlat = half / 111_320
    dlon = half / (111_320 * math.cos(math.radians(lat)))
    return Polygon(
        [
            (lon - dlon, lat - dlat),
            (lon + dlon, lat - dlat),
            (lon + dlon, lat + dlat),
            (lon - dlon, lat + dlat),
        ]
    )
