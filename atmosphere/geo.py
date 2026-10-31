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


def reverse_geocode(lat: float, lon: float, lang: str = "id") -> str | None:
    """Alamat dari koordinat lewat OpenStreetMap Nominatim (gratis, maks. 1 permintaan/detik).

    Mengembalikan None jika gagal (offline, timeout, dll) supaya aplikasi tetap jalan.
    """
    import requests

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": f"{lat:.6f}", "lon": f"{lon:.6f}", "zoom": 17,
                    "accept-language": lang},
            headers={"User-Agent": "AtmoSphereSim/2.0 (Hacktoberfest Batam; github.com/Vero9999/AtmoSphere-Sim-v2)"},
            timeout=6,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return None
    addr = data.get("address") or {}
    parts = [
        addr.get("road"),
        addr.get("neighbourhood") or addr.get("hamlet") or addr.get("quarter"),
        addr.get("village") or addr.get("suburb"),
        addr.get("city_district") or addr.get("district"),
        addr.get("city") or addr.get("town") or addr.get("county"),
    ]
    seen, out = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return ", ".join(out) or data.get("display_name")


def dissolve_cells(geojson: dict) -> list:
    """Gabungkan sel grid per (tutupan lahan, kawasan lindung) supaya peta jauh lebih ringan."""
    from collections import defaultdict

    import shapely
    from shapely.geometry import mapping, shape
    from shapely.ops import unary_union

    groups = defaultdict(list)
    for f in geojson["features"]:
        p = f["properties"]
        groups[(p["tutupan_lahan"], bool(p.get("kawasan_lindung")))].append(shape(f["geometry"]))
    out = []
    for (cover, protected), geoms in groups.items():
        merged = shapely.set_precision(unary_union(geoms), 1e-5)
        out.append({"cover": cover, "protected": protected, "geometry": mapping(merged)})
    return out
