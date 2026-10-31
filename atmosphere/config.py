"""Konstanta, tabel koefisien, dan asumsi model.

Semua angka di sini adalah asumsi awal untuk prototipe. Setiap tabel diberi
catatan sumber atau status "ASUMSI" supaya tim mudah memverifikasi dan
menggantinya dengan nilai yang lebih tepat untuk Batam.
"""

# Label tutupan lahan yang dipakai di seluruh aplikasi.
LAND_COVER_LABELS = {
    "hutan": "Hutan",
    "semak": "Semak belukar",
    "lahan_terbuka": "Lahan terbuka",
    "permukiman": "Permukiman/komersial",
    "industri": "Industri",
    "mangrove": "Mangrove",
    "badan_air": "Badan air/waduk",
}

LAND_COVER_COLORS = {
    "hutan": "#2d6a4f",
    "semak": "#95d5b2",
    "lahan_terbuka": "#e9c46a",
    "permukiman": "#e76f51",
    "industri": "#6c757d",
    "mangrove": "#1b998b",
    "badan_air": "#4ea8de",
}

# --- Hidrologi: SCS Curve Number (USDA TR-55) -------------------------------
# Nilai per kelompok hidrologi tanah (A, B, C, D).
# Sumber: USDA NRCS TR-55 (1986). Mangrove: ASUMSI (diperlakukan seperti lahan basah).
CURVE_NUMBER = {
    "hutan": {"A": 30, "B": 55, "C": 70, "D": 77},
    "semak": {"A": 35, "B": 56, "C": 70, "D": 77},
    "lahan_terbuka": {"A": 77, "B": 86, "C": 91, "D": 94},
    "permukiman": {"A": 77, "B": 85, "C": 90, "D": 92},
    "industri": {"A": 81, "B": 88, "C": 91, "D": 93},
    "mangrove": {"A": 70, "B": 80, "C": 85, "D": 88},
    "badan_air": {"A": 98, "B": 98, "C": 98, "D": 98},
    # Kategori khusus untuk kondisi setelah pembangunan
    "rth": {"A": 39, "B": 61, "C": 74, "D": 80},  # ruang terbuka hijau, rumput baik
    "kedap_air": {"A": 98, "B": 98, "C": 98, "D": 98},  # atap, jalan, parkir
}

# Hujan rencana harian (mm). ASUMSI: hujan lebat harian di Batam.
# TODO: ganti dengan analisis frekuensi data BMKG Stasiun Hang Nadim.
DESIGN_STORM_MM = 100.0

# --- Erosi: USLE --------------------------------------------------------------
# Faktor C (penutupan vegetasi). Sumber umum: Arsyad (2010), Abdurachman dkk.
# Nilai permukiman/industri: ASUMSI.
USLE_C = {
    "hutan": 0.001,
    "semak": 0.01,
    "lahan_terbuka": 1.0,
    "permukiman": 0.05,
    "industri": 0.05,
    "mangrove": 0.001,
    "badan_air": 0.0,
    "rth": 0.01,
    "kedap_air": 0.0,
}
USLE_SLOPE_LENGTH_M = 50.0  # ASUMSI panjang lereng rata-rata
USLE_P_WITH_CONTROL = 0.5  # ASUMSI: silt fence/terasering sementara

# Kelas Tingkat Bahaya Erosi (ton/ha/tahun). Sumber: Departemen Kehutanan (1998).
EROSION_CLASSES = [
    (15, "sangat ringan"),
    (60, "ringan"),
    (180, "sedang"),
    (480, "berat"),
    (float("inf"), "sangat berat"),
]

# --- Kebutuhan dasar penghuni -------------------------------------------------
WATER_L_PER_PERSON_DAY = 150  # Kriteria perencanaan air minum perkotaan (Ditjen Cipta Karya)
WASTEWATER_FRACTION = 0.8  # 80% air bersih menjadi air limbah
WASTE_KG_PER_PERSON_DAY = 0.7  # ASUMSI, kisaran SNI 19-3964-1994 untuk kota sedang/besar
DEFAULT_PERSONS_PER_UNIT = 4

# --- Stok karbon biomassa (ton C/ha, atas + bawah permukaan) ------------------
# ASUMSI kasar dari kisaran IPCC 2006 Vol. 4 untuk hutan tropis sekunder.
# Mangrove belum termasuk karbon tanah (yang sebenarnya jauh lebih besar).
CARBON_STOCK_T_PER_HA = {
    "hutan": 120,
    "semak": 20,
    "lahan_terbuka": 2,
    "permukiman": 5,
    "industri": 3,
    "mangrove": 150,
    "badan_air": 0,
    "rth": 3,
    "kedap_air": 0,
}
CO2_PER_C = 44 / 12

# --- Ambang tingkat dampak (rendah/sedang/tinggi) -----------------------------
# ASUMSI untuk prototipe. Format: (batas_atas_rendah, batas_atas_sedang).
IMPACT_THRESHOLDS = {
    "limpasan_kenaikan_pct": (20, 60),
    "air_bersih_m3_hari": (10, 100),
    "sampah_kg_hari": (100, 1000),
    "emisi_karbon_tco2": (50, 500),
}

# --- Pemakai bangunan per jenis kegiatan --------------------------------------
# Air (L/orang/hari) dan sampah (kg/orang/hari). Rumah/ruko: Ditjen Cipta Karya.
# Kantor, hotel, mal: ASUMSI dari kisaran SNI 03-7065-2005 (perlu verifikasi).
OCCUPANCY = {
    "perumahan": {"water_l": 150, "waste_kg": 0.7},
    "ruko": {"water_l": 150, "waste_kg": 0.7},
    "kantor": {"water_l": 50, "waste_kg": 0.3},
    "hotel": {"water_l": 250, "waste_kg": 1.0},
    "mal": {"water_l": 10, "waste_kg": 0.1},
    "lainnya": {"water_l": 50, "waste_kg": 0.3},
}
HOTEL_GUESTS_PER_ROOM = 2  # ASUMSI
