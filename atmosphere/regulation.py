"""Indikasi dokumen lingkungan (AMDAL / UKL-UPL / SPPL).

PERINGATAN: ambang di bawah ini adalah PLACEHOLDER untuk prototipe dan WAJIB
diverifikasi terhadap PermenLHK No. 4 Tahun 2021 (lampiran I) dan konsultasi
dengan DLH Kota Batam. Hasilnya hanya indikasi, bukan keputusan hukum.
"""

from .i18n import fmt, t

# PLACEHOLDER, perlu verifikasi.
BUILDING_AMDAL_LAND_M2 = 50_000  # luas lahan gedung >= 5 ha
BUILDING_AMDAL_FLOOR_M2 = 10_000  # luas total lantai >= 10.000 m²
HOUSING_AMDAL_LAND_M2 = 250_000  # perumahan kota besar >= 25 ha
UKL_UPL_LAND_M2 = 5_000  # di bawah ini dianggap SPPL


def indicate_building_document(land_m2: float, floor_m2: float, existing, lang: str = "id") -> dict:
    reasons = []
    if existing.in_protected_area or existing.touches_mangrove:
        reasons.append(t("r.sensitive", lang))
    if land_m2 >= BUILDING_AMDAL_LAND_M2:
        reasons.append(t("r.land", lang, ha=fmt(BUILDING_AMDAL_LAND_M2 / 10_000, 0, lang)))
    if floor_m2 >= BUILDING_AMDAL_FLOOR_M2:
        reasons.append(t("r.floor", lang, m2=fmt(BUILDING_AMDAL_FLOOR_M2, 0, lang)))
    if land_m2 >= HOUSING_AMDAL_LAND_M2:
        reasons.append(t("r.housing", lang))

    if reasons:
        doc = "AMDAL"
    elif land_m2 >= UKL_UPL_LAND_M2:
        doc = "UKL-UPL"
        reasons.append(t("r.medium", lang))
    else:
        doc = "SPPL"
        reasons.append(t("r.small", lang))
    return {"dokumen": doc, "alasan": reasons, "catatan": t("r.disclaimer", lang)}
