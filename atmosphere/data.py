"""Akses data kondisi lingkungan eksisting.

Data disimpan sebagai GeoJSON berisi sel-sel grid dengan atribut lingkungan.
Untuk area yang dipilih user, atribut dirata-ratakan berbobot luas irisan.
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import shape
from shapely.strtree import STRtree

from .geo import area_m2

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "batam_existing_dummy.geojson"


@dataclass
class ExistingCondition:
    area_m2: float
    land_cover_share: dict  # {tutupan_lahan: fraksi 0..1}
    slope_pct: float
    hsg: str  # kelompok hidrologi tanah A/B/C/D
    soil_k: float
    rainfall_mm_year: float
    population_density: float  # jiwa/km²
    pm25_ugm3: float
    in_protected_area: bool
    touches_mangrove: bool
    covered_fraction: float  # porsi area yang tercakup data
    is_dummy: bool
    data_date: str
    corrections: list = field(default_factory=list)  # koreksi dari user

    @property
    def dominant_land_cover(self) -> str:
        return max(self.land_cover_share, key=self.land_cover_share.get)

    def to_dict(self) -> dict:
        return {
            "luas_m2": round(self.area_m2),
            "tutupan_lahan": {k: round(v, 2) for k, v in self.land_cover_share.items()},
            "kemiringan_pct": round(self.slope_pct, 1),
            "kelompok_hidrologi_tanah": self.hsg,
            "curah_hujan_mm_tahun": round(self.rainfall_mm_year),
            "kepadatan_penduduk_jiwa_km2": round(self.population_density),
            "pm25_ugm3": round(self.pm25_ugm3, 1),
            "kawasan_lindung": self.in_protected_area,
            "mangrove": self.touches_mangrove,
            "data_dummy": self.is_dummy,
            "koreksi_user": self.corrections,
        }


class ExistingDataStore:
    def __init__(self, path: Path = DATA_PATH):
        with open(path, encoding="utf-8") as f:
            self.geojson = json.load(f)
        self.features = self.geojson["features"]
        self.geoms = [shape(f["geometry"]) for f in self.features]
        self.tree = STRtree(self.geoms)
        self.is_dummy = any("DUMMY" in f["properties"].get("sumber", "") for f in self.features)

    def query(self, polygon) -> ExistingCondition | None:
        hits = self.tree.query(polygon, predicate="intersects")
        if len(hits) == 0:
            return None

        weights = []
        for i in hits:
            inter = self.geoms[i].intersection(polygon)
            if not inter.is_empty:
                weights.append((self.features[i]["properties"], inter.area))
        total = sum(w for _, w in weights)
        if total == 0:
            return None

        cover = defaultdict(float)
        hsg = defaultdict(float)
        num = defaultdict(float)
        numeric_keys = {
            "kemiringan_pct": "slope",
            "erodibilitas_k": "k",
            "curah_hujan_mm_tahun": "rain",
            "kepadatan_penduduk_jiwa_km2": "pop",
            "pm25_ugm3": "pm25",
        }
        protected = mangrove = dummy = False
        dates = set()
        for props, w in weights:
            frac = w / total
            cover[props["tutupan_lahan"]] += frac
            hsg[props["kelompok_hidrologi_tanah"]] += frac
            for key, alias in numeric_keys.items():
                num[alias] += props[key] * frac
            protected |= bool(props.get("kawasan_lindung"))
            mangrove |= props["tutupan_lahan"] == "mangrove"
            dummy |= "DUMMY" in props.get("sumber", "")
            dates.add(props.get("tanggal_data", "-"))

        return ExistingCondition(
            area_m2=area_m2(polygon),
            land_cover_share=dict(cover),
            slope_pct=num["slope"],
            hsg=max(hsg, key=hsg.get),
            soil_k=num["k"],
            rainfall_mm_year=num["rain"],
            population_density=num["pop"],
            pm25_ugm3=num["pm25"],
            in_protected_area=protected,
            touches_mangrove=mangrove,
            covered_fraction=min(1.0, total / polygon.area) if polygon.area else 0,
            is_dummy=dummy,
            data_date=", ".join(sorted(dates)),
        )
