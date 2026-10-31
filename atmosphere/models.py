"""Model dampak fisik sederhana. Semua fungsi murni (tanpa I/O) agar mudah diuji."""

import math

from . import config as C


def level_from_thresholds(value: float, key: str) -> str:
    low, mid = C.IMPACT_THRESHOLDS[key]
    if value < low:
        return "rendah"
    if value < mid:
        return "sedang"
    return "tinggi"


# --- Hidrologi ----------------------------------------------------------------
def curve_number(cover: str, hsg: str) -> float:
    return C.CURVE_NUMBER[cover][hsg]


def composite_cn(shares: dict, hsg: str) -> float:
    """CN gabungan berbobot luas."""
    return sum(frac * curve_number(cover, hsg) for cover, frac in shares.items())


def scs_runoff_mm(rain_mm: float, cn: float) -> float:
    """Limpasan langsung (mm) metode SCS Curve Number."""
    cn = min(max(cn, 1.0), 100.0)
    if cn >= 100:
        return rain_mm
    s = 25400 / cn - 254
    ia = 0.2 * s
    if rain_mm <= ia:
        return 0.0
    return (rain_mm - ia) ** 2 / (rain_mm - ia + s)


# --- Erosi --------------------------------------------------------------------
def rainfall_erosivity(annual_mm: float) -> float:
    """Faktor R dari curah hujan tahunan, rumus Lenvain (1975), dipakai luas di Indonesia.

    Penyederhanaan: hujan dianggap merata per bulan.
    """
    monthly_cm = annual_mm / 10 / 12
    return 12 * 2.21 * monthly_cm**1.36


def ls_factor(slope_pct: float, length_m: float = C.USLE_SLOPE_LENGTH_M) -> float:
    s = max(slope_pct, 0.0)
    return math.sqrt(length_m / 22.1) * (0.065 + 0.045 * s + 0.0065 * s**2)


def usle(r: float, k: float, ls: float, c: float, p: float = 1.0) -> float:
    """Laju erosi tanah (ton/ha/tahun)."""
    return r * k * ls * c * p


def composite_c(shares: dict) -> float:
    return sum(frac * C.USLE_C[cover] for cover, frac in shares.items())


def erosion_class(rate_t_ha_yr: float) -> str:
    for upper, label in C.EROSION_CLASSES:
        if rate_t_ha_yr < upper:
            return label
    return C.EROSION_CLASSES[-1][1]


def erosion_level(rate_t_ha_yr: float) -> str:
    cls = erosion_class(rate_t_ha_yr)
    if cls in ("sangat ringan", "ringan"):
        return "rendah"
    if cls == "sedang":
        return "sedang"
    return "tinggi"


# --- Karbon -------------------------------------------------------------------
def carbon_stock_t(shares: dict, area_ha: float) -> float:
    """Stok karbon biomassa (ton C)."""
    return sum(frac * C.CARBON_STOCK_T_PER_HA[cover] for cover, frac in shares.items()) * area_ha


# --- Kebutuhan penghuni -------------------------------------------------------
def water_demand_m3_day(persons: float) -> float:
    return persons * C.WATER_L_PER_PERSON_DAY / 1000


def waste_kg_day(persons: float) -> float:
    return persons * C.WASTE_KG_PER_PERSON_DAY
