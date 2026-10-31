"""Indikasi dokumen lingkungan (AMDAL / UKL-UPL / SPPL).

PERINGATAN: ambang di bawah ini adalah PLACEHOLDER untuk prototipe dan WAJIB
diverifikasi terhadap PermenLHK No. 4 Tahun 2021 (lampiran I) dan konsultasi
dengan DLH Kota Batam. Hasilnya hanya indikasi, bukan keputusan hukum.
"""

DISCLAIMER = (
    "Ini indikasi awal, bukan keputusan resmi. Kepastian jenis dokumen lingkungan "
    "ditentukan melalui sistem perizinan (OSS) dan DLH Kota Batam."
)

# PLACEHOLDER, perlu verifikasi.
BUILDING_AMDAL_LAND_M2 = 50_000  # luas lahan gedung >= 5 ha
BUILDING_AMDAL_FLOOR_M2 = 10_000  # luas total lantai >= 10.000 m²
HOUSING_AMDAL_LAND_M2 = 250_000  # perumahan kota besar >= 25 ha
UKL_UPL_LAND_M2 = 5_000  # di bawah ini dianggap SPPL


def indicate_building_document(land_m2: float, floor_m2: float, existing) -> dict:
    reasons = []
    if existing.in_protected_area or existing.touches_mangrove:
        reasons.append("Lokasi berada di/berbatasan dengan kawasan lindung atau mangrove.")
    if land_m2 >= BUILDING_AMDAL_LAND_M2:
        reasons.append(f"Luas lahan ≥ {BUILDING_AMDAL_LAND_M2 / 10_000:g} ha.")
    if floor_m2 >= BUILDING_AMDAL_FLOOR_M2:
        reasons.append(f"Luas total lantai ≥ {BUILDING_AMDAL_FLOOR_M2:,} m².".replace(",", "."))
    if land_m2 >= HOUSING_AMDAL_LAND_M2:
        reasons.append("Skala perumahan/kawasan besar.")

    if reasons:
        doc = "AMDAL"
    elif land_m2 >= UKL_UPL_LAND_M2:
        doc = "UKL-UPL"
        reasons.append("Skala menengah, di bawah ambang AMDAL.")
    else:
        doc = "SPPL"
        reasons.append("Skala kecil dan tidak di kawasan sensitif.")
    return {"dokumen": doc, "alasan": reasons, "catatan": DISCLAIMER}
