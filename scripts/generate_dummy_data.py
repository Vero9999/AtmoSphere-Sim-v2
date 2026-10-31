"""Membuat data kondisi eksisting DUMMY untuk Kota Batam (Pulau Batam).

Data ini BUKAN data asli. Garis pantai, lokasi waduk, kawasan industri, dan
pusat kota hanya perkiraan kasar agar polanya terlihat realistis untuk demo.
Ganti dengan data asli (lihat docs/DESIGN.md bagian "Sumber data").

Jalankan:  python scripts/generate_dummy_data.py
"""

import json
import math
import random
from pathlib import Path

from shapely.geometry import Point, Polygon, box, mapping

OUT = Path(__file__).resolve().parent.parent / "data" / "batam_existing_dummy.geojson"
CELL = 0.005  # derajat, ±550 m
TODAY = "2026-10-25"

# Garis pantai Pulau Batam yang sangat disederhanakan (lon, lat)
OUTLINE = Polygon(
    [
        (103.94, 1.10), (103.96, 1.15), (104.00, 1.17), (104.04, 1.16),
        (104.08, 1.19), (104.13, 1.19), (104.15, 1.15), (104.13, 1.10),
        (104.12, 1.05), (104.08, 1.02), (104.04, 0.99), (104.00, 1.01),
        (103.96, 1.03), (103.93, 1.06),
    ]
)

# (nama, lon, lat, radius derajat)
RESERVOIRS = [
    ("Duriangkang", 104.055, 1.035, 0.012),
    ("Muka Kuning", 104.035, 1.085, 0.006),
    ("Sei Harapan", 103.975, 1.130, 0.004),
    ("Sei Ladi", 104.005, 1.125, 0.004),
]
URBAN = [
    ("Nagoya/Lubuk Baja", 104.010, 1.145, 0.025),
    ("Batam Centre", 104.050, 1.130, 0.025),
    ("Sekupang/Tiban", 103.970, 1.120, 0.020),
    ("Batu Aji/Sagulung", 103.980, 1.060, 0.022),
    ("Bengkong", 104.030, 1.150, 0.015),
]
INDUSTRY = [
    ("Batamindo", 104.040, 1.070, 0.012),
    ("Kabil", 104.115, 1.065, 0.012),
    ("Tanjung Uncang", 103.945, 1.065, 0.010),
    ("Batu Ampar", 104.000, 1.165, 0.008),
]


def dist(x, y, cx, cy):
    return math.hypot(x - cx, y - cy)


def classify(x, y, coast_d, rng):
    """Kembalikan (tutupan_lahan, kawasan_lindung)."""
    for _, cx, cy, r in RESERVOIRS:
        if dist(x, y, cx, cy) < r:
            return "badan_air", True
    if any(dist(x, y, cx, cy) < r * 2.2 for _, cx, cy, r in RESERVOIRS):
        return rng.choices(["hutan", "semak"], [0.8, 0.2])[0], True
    if any(dist(x, y, cx, cy) < r for _, cx, cy, r in INDUSTRY):
        return rng.choices(["industri", "lahan_terbuka", "semak"], [0.75, 0.15, 0.10])[0], False
    for _, cx, cy, r in URBAN:
        d = dist(x, y, cx, cy)
        if d < r:
            w = 1 - d / r
            p_urban = 0.4 + 0.55 * w
            return rng.choices(
                ["permukiman", "lahan_terbuka", "semak"], [p_urban, (1 - p_urban) * 0.5, (1 - p_urban) * 0.5]
            )[0], False
    if coast_d < 0.006 and rng.random() < 0.45:
        return "mangrove", False
    return rng.choices(["semak", "hutan", "lahan_terbuka", "permukiman"], [0.45, 0.25, 0.20, 0.10])[0], False


SLOPE_RANGE = {
    "hutan": (8, 30), "semak": (4, 20), "lahan_terbuka": (3, 25), "permukiman": (1, 10),
    "industri": (1, 6), "mangrove": (0, 2), "badan_air": (0, 0),
}
POP_RANGE = {
    "permukiman": (6000, 14000), "industri": (300, 1500), "lahan_terbuka": (50, 400),
}
PM25_RANGE = {"industri": (25, 35), "permukiman": (18, 28)}


def main():
    rng = random.Random(42)
    minx, miny, maxx, maxy = OUTLINE.bounds
    features = []
    y = miny
    idx = 0
    while y < maxy:
        x = minx
        while x < maxx:
            cell = box(x, y, x + CELL, y + CELL).intersection(OUTLINE)
            if not cell.is_empty and cell.area > (CELL * CELL) * 0.15:
                c = cell.centroid
                coast_d = OUTLINE.exterior.distance(Point(c.x, c.y))
                cover, protected = classify(c.x, c.y, coast_d, rng)
                lo, hi = SLOPE_RANGE[cover]
                hsg = "D" if cover in ("mangrove", "badan_air") else rng.choices("CDB", [0.75, 0.15, 0.10])[0]
                features.append(
                    {
                        "type": "Feature",
                        "geometry": json.loads(json.dumps(mapping(cell.simplify(0.00005)), default=list)),
                        "properties": {
                            "id": idx,
                            "tutupan_lahan": cover,
                            "kemiringan_pct": round(rng.uniform(lo, hi), 1),
                            "kelompok_hidrologi_tanah": hsg,
                            "erodibilitas_k": round(0.1 if cover == "mangrove" else rng.uniform(0.18, 0.32), 3),
                            "curah_hujan_mm_tahun": round(2450 + (1.2 - c.y) * 800 + rng.uniform(-50, 50)),
                            "kepadatan_penduduk_jiwa_km2": round(rng.uniform(*POP_RANGE.get(cover, (0, 150)))),
                            "pm25_ugm3": round(rng.uniform(*PM25_RANGE.get(cover, (10, 18))), 1),
                            "kawasan_lindung": protected,
                            "sumber": "DUMMY - bukan data asli",
                            "tanggal_data": TODAY,
                        },
                    }
                )
                idx += 1
            x += CELL
        y += CELL

    def round_coords(obj):
        if isinstance(obj, (list, tuple)):
            if obj and isinstance(obj[0], (int, float)):
                return [round(v, 5) for v in obj]
            return [round_coords(o) for o in obj]
        return obj

    for f in features:
        f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, separators=(",", ":"))
    print(f"Tersimpan {len(features)} sel ke {OUT}")


if __name__ == "__main__":
    main()
