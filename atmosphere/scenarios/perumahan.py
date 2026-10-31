"""Skenario: pembangunan perumahan, ruko, atau gedung (termasuk cut and fill)."""

from .. import config as C
from .. import models as M
from ..regulation import indicate_building_document
from ..results import AssessmentResult, ComponentImpact
from .base import Param, Scenario


def _fmt(x: float, nd: int = 0) -> str:
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


class PerumahanScenario(Scenario):
    key = "perumahan"
    label = "Perumahan / ruko / gedung"
    description = "Membangun rumah, perumahan, ruko, atau gedung, termasuk pemotongan bukit (cut and fill)."
    example_text = (
        "Saya mau bangun 20 unit ruko 3 lantai di lahan 4.000 m², "
        "tapaknya sekitar 2.400 m² dan jalan/parkir 800 m². "
        "Lahannya berbukit jadi perlu cut and fill. Konstruksi 12 bulan."
    )
    params = [
        Param("luas_lahan_m2", "Luas lahan", "float", 1000, "Total luas area kegiatan.", "m²", 1),
        Param("luas_tapak_bangunan_m2", "Luas tapak bangunan", "float", 600, "Luas lantai dasar/atap.", "m²"),
        Param("luas_perkerasan_m2", "Luas jalan & parkir", "float", 200, "Permukaan diaspal/dibeton.", "m²"),
        Param("jumlah_lantai", "Jumlah lantai", "int", 2, "", "lantai", 1),
        Param("jumlah_unit", "Jumlah unit", "int", 5, "Rumah/ruko/unit hunian.", "unit"),
        Param("penghuni_per_unit", "Penghuni per unit", "float", C.DEFAULT_PERSONS_PER_UNIT, "", "orang"),
        Param("cut_and_fill", "Ada cut and fill (potong/urug bukit)", "bool", False),
        Param("durasi_konstruksi_bulan", "Durasi konstruksi", "int", 12, "", "bulan", 1),
        Param("pengendali_erosi", "Pakai pengendali erosi (silt fence/terasering)", "bool", False),
        Param("sumur_resapan_m3", "Kapasitas sumur resapan/kolam retensi", "float", 0, "", "m³"),
    ]

    def defaults(self, area_m2: float | None = None) -> dict:
        d = super().defaults()
        if area_m2:
            d["luas_lahan_m2"] = round(area_m2)
            d["luas_tapak_bangunan_m2"] = round(area_m2 * 0.6)
            d["luas_perkerasan_m2"] = round(area_m2 * 0.2)
        return d

    def run(self, existing, p: dict) -> AssessmentResult:
        area = max(float(p["luas_lahan_m2"]), 1.0)
        ha = area / 10_000
        impervious = min(area, p["luas_tapak_bangunan_m2"] + p["luas_perkerasan_m2"])
        imp_frac = impervious / area
        after_shares = {"kedap_air": imp_frac, "rth": 1 - imp_frac}
        hsg = existing.hsg
        components = []

        # 1. Limpasan air hujan / risiko genangan
        q_before = M.scs_runoff_mm(C.DESIGN_STORM_MM, M.composite_cn(existing.land_cover_share, hsg))
        q_after = M.scs_runoff_mm(C.DESIGN_STORM_MM, M.composite_cn(after_shares, hsg))
        v_before = q_before / 1000 * area
        v_after_gross = q_after / 1000 * area
        v_after = max(0.0, v_after_gross - p["sumur_resapan_m3"])
        increase = (v_after - v_before) / v_before * 100 if v_before > 0 else (100.0 if v_after > 0 else 0.0)
        extra = max(0.0, v_after - v_before)
        components.append(
            ComponentImpact(
                key="limpasan",
                phase="operasional",
                name="Limpasan air hujan (risiko genangan/banjir)",
                level=M.level_from_thresholds(increase, "limpasan_kenaikan_pct"),
                summary=(
                    f"Saat hujan lebat {_fmt(C.DESIGN_STORM_MM)} mm, air yang mengalir di permukaan "
                    f"berubah dari ±{_fmt(v_before)} m³ menjadi ±{_fmt(v_after)} m³ "
                    f"({'+' if increase >= 0 else ''}{_fmt(increase)}%). "
                    f"{_fmt(imp_frac * 100)}% lahan akan tertutup bangunan/perkerasan."
                ),
                before=v_before,
                after=v_after,
                unit="m³ per kejadian hujan",
                mitigation=(
                    [
                        f"Sediakan sumur resapan/kolam retensi tambahan ±{_fmt(extra)} m³.",
                        "Pertahankan minimal 30% lahan sebagai ruang terbuka hijau.",
                        "Gunakan paving berpori untuk area parkir.",
                    ]
                    if extra > 0
                    else ["Pertahankan kapasitas resapan yang sudah direncanakan."]
                ),
            )
        )

        # 2. Erosi selama konstruksi
        r = M.rainfall_erosivity(existing.rainfall_mm_year)
        ls = M.ls_factor(existing.slope_pct)
        p_factor = C.USLE_P_WITH_CONTROL if p["pengendali_erosi"] else 1.0
        a_before = M.usle(r, existing.soil_k, ls, M.composite_c(existing.land_cover_share))
        a_constr = M.usle(r, existing.soil_k, ls, C.USLE_C["lahan_terbuka"], p_factor)
        if not p["cut_and_fill"]:
            a_constr *= 0.5  # ASUMSI: tanpa cut and fill, lahan terbuka hanya sebagian dan lebih singkat
        sediment_t = a_constr * ha * p["durasi_konstruksi_bulan"] / 12
        components.append(
            ComponentImpact(
                key="erosi",
                phase="konstruksi",
                name="Erosi & sedimentasi saat konstruksi",
                level=M.erosion_level(a_constr),
                summary=(
                    f"Kemiringan lahan rata-rata {_fmt(existing.slope_pct, 1)}%. Saat tanah dibuka, laju erosi "
                    f"diperkirakan ±{_fmt(a_constr)} ton/ha/tahun (kelas {M.erosion_class(a_constr)}), "
                    f"dibanding ±{_fmt(a_before, 1)} ton/ha/tahun sekarang. Total sedimen selama "
                    f"{p['durasi_konstruksi_bulan']} bulan ±{_fmt(sediment_t)} ton yang bisa masuk ke saluran, "
                    "sungai, atau waduk."
                ),
                before=a_before,
                after=a_constr,
                unit="ton/ha/tahun",
                mitigation=[
                    "Pasang silt fence dan kolam pengendap sedimen sebelum membuka lahan.",
                    "Buka lahan bertahap, jangan sekaligus.",
                    "Tanam penutup tanah (rumput) di lereng secepatnya.",
                ]
                + (["Hindari pekerjaan tanah saat musim hujan (Nov-Jan)."] if p["cut_and_fill"] else []),
            )
        )

        # 3-5. Kebutuhan penghuni
        persons = p["jumlah_unit"] * p["penghuni_per_unit"]
        water = M.water_demand_m3_day(persons)
        components.append(
            ComponentImpact(
                key="air_bersih",
                phase="operasional",
                name="Kebutuhan air bersih",
                level=M.level_from_thresholds(water, "air_bersih_m3_hari"),
                summary=(
                    f"±{_fmt(persons)} penghuni membutuhkan ±{_fmt(water, 1)} m³ air/hari. "
                    "Air baku Batam bergantung pada waduk tadah hujan, sehingga tambahan kebutuhan ini penting diperhatikan."
                ),
                after=water,
                unit="m³/hari",
                mitigation=["Pasang penampung air hujan.", "Gunakan keran dan kloset hemat air."],
            )
        )
        wastewater = water * C.WASTEWATER_FRACTION
        components.append(
            ComponentImpact(
                key="air_limbah",
                phase="operasional",
                name="Air limbah domestik",
                level=M.level_from_thresholds(water, "air_bersih_m3_hari"),
                summary=f"Menghasilkan ±{_fmt(wastewater, 1)} m³ air limbah/hari.",
                after=wastewater,
                unit="m³/hari",
                mitigation=["Gunakan septic tank kedap/biofilter atau IPAL komunal sesuai skala."],
            )
        )
        waste = M.waste_kg_day(persons)
        components.append(
            ComponentImpact(
                key="sampah",
                phase="operasional",
                name="Timbulan sampah",
                level=M.level_from_thresholds(waste, "sampah_kg_hari"),
                summary=f"Menghasilkan ±{_fmt(waste)} kg sampah/hari.",
                after=waste,
                unit="kg/hari",
                mitigation=["Sediakan TPS3R / pemilahan organik-anorganik.", "Kerja sama dengan bank sampah."],
            )
        )

        # 6. Emisi karbon dari pembukaan lahan
        stock_before = M.carbon_stock_t(existing.land_cover_share, ha)
        stock_after = M.carbon_stock_t(after_shares, ha)
        co2 = max(0.0, stock_before - stock_after) * C.CO2_PER_C
        components.append(
            ComponentImpact(
                key="karbon",
                phase="konstruksi",
                name="Emisi karbon dari pembukaan lahan",
                level=M.level_from_thresholds(co2, "emisi_karbon_tco2"),
                summary=(
                    f"Hilangnya vegetasi melepas ±{_fmt(co2)} ton CO₂, setara emisi ±{_fmt(co2 / 2.3)} mobil "
                    "selama setahun."
                ),
                before=stock_before * C.CO2_PER_C,
                after=stock_after * C.CO2_PER_C,
                unit="ton CO₂ tersimpan",
                mitigation=["Pertahankan pohon besar yang ada.", "Tanam pohon peneduh di RTH dan sepanjang jalan."],
            )
        )

        # 7. Kawasan sensitif
        if existing.in_protected_area or existing.touches_mangrove:
            what = []
            if existing.in_protected_area:
                what.append("kawasan lindung/daerah tangkapan waduk")
            if existing.touches_mangrove:
                what.append("ekosistem mangrove")
            components.append(
                ComponentImpact(
                    key="kawasan_sensitif",
                    name="Kawasan sensitif",
                    level="tinggi",
                    summary=f"Area menyentuh {' dan '.join(what)}. Kegiatan di sini berisiko tinggi dan perizinannya ketat.",
                    mitigation=["Pertimbangkan pindah lokasi atau geser batas kegiatan keluar dari kawasan sensitif."],
                )
            )

        floor_total = p["luas_tapak_bangunan_m2"] * p["jumlah_lantai"]
        timeline = build_timeline(
            components,
            construction_months=p["durasi_konstruksi_bulan"],
            sediment_t=sediment_t,
            extra_runoff_m3_year=extra / C.DESIGN_STORM_MM * existing.rainfall_mm_year,
            water_m3_day=water,
            wastewater_m3_day=wastewater,
            waste_kg_day=waste,
            co2_t=co2,
        )
        return AssessmentResult(
            scenario_key=self.key,
            scenario_label=self.label,
            params=dict(p),
            existing=existing.to_dict(),
            components=components,
            regulation=indicate_building_document(area, floor_total, existing),
            assumptions=[
                f"Hujan rencana {C.DESIGN_STORM_MM:g} mm/hari (asumsi, belum dari analisis data BMKG).",
                f"Kebutuhan air {C.WATER_L_PER_PERSON_DAY} L/orang/hari, sampah {C.WASTE_KG_PER_PERSON_DAY} kg/orang/hari.",
                "Stok karbon mangrove belum memasukkan karbon tanah, jadi emisi sebenarnya bisa jauh lebih besar.",
                "Ambang rendah/sedang/tinggi masih asumsi tim, belum baku mutu resmi.",
            ]
            + ["Prediksi per periode: limpasan tahunan diskalakan dari hujan rencana ke curah hujan tahunan (asumsi kasar)."]
            + (["Data kondisi eksisting masih DUMMY, bukan data asli."] if existing.is_dummy else []),
            timeline=timeline,
        )


PERIODS = [("konstruksi", "Saat konstruksi", 0), ("1th", "1 tahun", 1), ("5th", "5 tahun", 5), ("10th", "10 tahun", 10)]
_LEVEL_SCORE = {"rendah": 0, "sedang": 50, "tinggi": 100}


def build_timeline(components, construction_months, sediment_t, extra_runoff_m3_year,
                   water_m3_day, wastewater_m3_day, waste_kg_day, co2_t) -> list:
    """Akumulasi dampak per periode: saat konstruksi, lalu 1/5/10 tahun setelah bangunan dipakai.

    Indeks risiko periode = rata-rata skor komponen yang aktif di fase itu (0-100).
    Dampak yang menumpuk (air, limbah, sampah, limpasan) dijumlahkan sepanjang waktu.
    """
    def index(phase):
        active = [c for c in components if c.phase in (phase, "semua")]
        return round(sum(_LEVEL_SCORE[c.level] for c in active) / len(active)) if active else 0

    out = []
    for key, label, years in PERIODS:
        if years == 0:
            out.append({
                "key": key, "label": label, "tahun": round(construction_months / 12, 2),
                "indeks_risiko": index("konstruksi"),
                "sedimen_ton": sediment_t, "karbon_tco2": co2_t,
                "limpasan_tambahan_m3": 0.0, "air_bersih_m3": 0.0, "air_limbah_m3": 0.0, "sampah_ton": 0.0,
            })
        else:
            days = 365 * years
            out.append({
                "key": key, "label": label, "tahun": years,
                "indeks_risiko": index("operasional"),
                "sedimen_ton": sediment_t, "karbon_tco2": co2_t,
                "limpasan_tambahan_m3": extra_runoff_m3_year * years,
                "air_bersih_m3": water_m3_day * days,
                "air_limbah_m3": wastewater_m3_day * days,
                "sampah_ton": waste_kg_day * days / 1000,
            })
    return out
