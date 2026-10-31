"""Skenario bangunan: rumah, ruko, kantor, hotel, mal, dan lainnya.

Semua jenis memakai model fisik yang sama (limpasan, erosi, karbon, kawasan sensitif)
dari luas lahan dan bangunan. Yang berbeda hanya cara menghitung jumlah pemakai dan
kebutuhan air/sampah per orang (lihat `config.OCCUPANCY`).
"""

from .. import config as C
from .. import models as M
from ..i18n import fmt, t
from ..regulation import indicate_building_document
from ..results import AssessmentResult, ComponentImpact
from .base import Param, Scenario

SITE_PARAMS = [
    Param("luas_lahan_m2", "float", 1000, "m2", 1),
    Param("luas_tapak_bangunan_m2", "float", 600, "m2"),
    Param("luas_perkerasan_m2", "float", 200, "m2"),
    Param("jumlah_lantai", "int", 2, "lantai", 1),
]
CONSTRUCTION_PARAMS = [
    Param("cut_and_fill", "bool", False),
    Param("durasi_konstruksi_bulan", "int", 12, "bulan", 1),
    Param("pengendali_erosi", "bool", False),
    Param("sumur_resapan_m3", "float", 0, "m3"),
]


class BuildingScenario(Scenario):
    who = "orang"  # kunci i18n untuk sebutan pemakai
    occupant_params: list = []

    @property
    def params(self):
        return SITE_PARAMS + self.occupant_params + CONSTRUCTION_PARAMS

    def persons(self, p: dict) -> float:
        raise NotImplementedError

    def water_l_per_person(self, p: dict) -> float:
        return C.OCCUPANCY[self.key]["water_l"]

    def waste_kg_per_person(self, p: dict) -> float:
        return C.OCCUPANCY[self.key]["waste_kg"]

    def defaults(self, area_m2: float | None = None) -> dict:
        d = super().defaults()
        if area_m2:
            d["luas_lahan_m2"] = round(area_m2)
            d["luas_tapak_bangunan_m2"] = round(area_m2 * 0.6)
            d["luas_perkerasan_m2"] = round(area_m2 * 0.2)
        return d

    def run(self, existing, p: dict, lang: str = "id") -> AssessmentResult:
        f = lambda x, nd=0: fmt(x, nd, lang)  # noqa: E731
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
        v_after = max(0.0, q_after / 1000 * area - p["sumur_resapan_m3"])
        increase = (v_after - v_before) / v_before * 100 if v_before > 0 else (100.0 if v_after > 0 else 0.0)
        extra = max(0.0, v_after - v_before)
        components.append(ComponentImpact(
            key="limpasan",
            phase="semua",  # lahan terbuka saat konstruksi, lalu tertutup bangunan selamanya
            score=M.score_from_thresholds(increase, "limpasan_kenaikan_pct"),
            name=t("c.limpasan", lang),
            level=M.level_from_thresholds(increase, "limpasan_kenaikan_pct"),
            summary=t("c.limpasan.sum", lang, storm=f(C.DESIGN_STORM_MM), before=f(v_before), after=f(v_after),
                      sign="+" if increase >= 0 else "", pct=f(increase), imp=f(imp_frac * 100)),
            before=v_before,
            after=v_after,
            unit=t("c.limpasan.unit", lang),
            mitigation=(
                [t("c.limpasan.m1", lang, extra=f(extra)), t("c.limpasan.m2", lang), t("c.limpasan.m3", lang)]
                if extra > 0 else [t("c.limpasan.ok", lang)]
            ),
        ))

        # 2. Erosi selama konstruksi
        r = M.rainfall_erosivity(existing.rainfall_mm_year)
        ls = M.ls_factor(existing.slope_pct)
        p_factor = C.USLE_P_WITH_CONTROL if p["pengendali_erosi"] else 1.0
        a_before = M.usle(r, existing.soil_k, ls, M.composite_c(existing.land_cover_share))
        a_constr = M.usle(r, existing.soil_k, ls, C.USLE_C["lahan_terbuka"], p_factor)
        if not p["cut_and_fill"]:
            a_constr *= 0.5  # ASUMSI: tanpa cut and fill, lahan terbuka hanya sebagian dan lebih singkat
        sediment_t = a_constr * ha * p["durasi_konstruksi_bulan"] / 12
        components.append(ComponentImpact(
            key="erosi",
            phase="konstruksi",
            score=M.erosion_score(a_constr),
            name=t("c.erosi", lang),
            level=M.erosion_level(a_constr),
            summary=t("c.erosi.sum", lang, slope=f(existing.slope_pct, 1), rate=f(a_constr),
                      cls=t("ec." + M.erosion_class(a_constr), lang), before=f(a_before, 1),
                      months=p["durasi_konstruksi_bulan"], sed=f(sediment_t)),
            before=a_before,
            after=a_constr,
            unit=t("c.erosi.unit", lang),
            mitigation=[t("c.erosi.m1", lang), t("c.erosi.m2", lang), t("c.erosi.m3", lang)]
            + ([t("c.erosi.m4", lang)] if p["cut_and_fill"] else []),
        ))

        # 3-5. Kebutuhan pemakai bangunan
        persons = self.persons(p)
        water = persons * self.water_l_per_person(p) / 1000
        components.append(ComponentImpact(
            key="air_bersih",
            phase="operasional",
            score=M.score_from_thresholds(water, "air_bersih_m3_hari"),
            name=t("c.air_bersih", lang),
            level=M.level_from_thresholds(water, "air_bersih_m3_hari"),
            summary=t("c.air_bersih.sum", lang, persons=f(persons), who=t("who." + self.who, lang), water=f(water, 1)),
            after=water,
            unit="m³/hari" if lang == "id" else "m³/day",
            mitigation=[t("c.air_bersih.m1", lang), t("c.air_bersih.m2", lang)],
        ))
        wastewater = water * C.WASTEWATER_FRACTION
        components.append(ComponentImpact(
            key="air_limbah",
            phase="operasional",
            score=M.score_from_thresholds(water, "air_bersih_m3_hari"),
            name=t("c.air_limbah", lang),
            level=M.level_from_thresholds(water, "air_bersih_m3_hari"),
            summary=t("c.air_limbah.sum", lang, ww=f(wastewater, 1)),
            after=wastewater,
            unit="m³/hari" if lang == "id" else "m³/day",
            mitigation=[t("c.air_limbah.m1", lang)],
        ))
        waste = persons * self.waste_kg_per_person(p)
        components.append(ComponentImpact(
            key="sampah",
            phase="operasional",
            score=M.score_from_thresholds(waste, "sampah_kg_hari"),
            name=t("c.sampah", lang),
            level=M.level_from_thresholds(waste, "sampah_kg_hari"),
            summary=t("c.sampah.sum", lang, waste=f(waste)),
            after=waste,
            unit="kg/hari" if lang == "id" else "kg/day",
            mitigation=[t("c.sampah.m1", lang), t("c.sampah.m2", lang)],
        ))

        # 6. Emisi karbon dari pembukaan lahan
        stock_before = M.carbon_stock_t(existing.land_cover_share, ha)
        stock_after = M.carbon_stock_t(after_shares, ha)
        co2 = max(0.0, stock_before - stock_after) * C.CO2_PER_C
        components.append(ComponentImpact(
            key="karbon",
            phase="semua",  # vegetasi yang hilang tidak kembali; serapan karbonnya hilang permanen
            score=M.score_from_thresholds(co2, "emisi_karbon_tco2"),
            name=t("c.karbon", lang),
            level=M.level_from_thresholds(co2, "emisi_karbon_tco2"),
            summary=t("c.karbon.sum", lang, co2=f(co2), cars=f(co2 / 2.3)),
            before=stock_before * C.CO2_PER_C,
            after=stock_after * C.CO2_PER_C,
            unit=t("c.karbon.unit", lang),
            mitigation=[t("c.karbon.m1", lang), t("c.karbon.m2", lang)],
        ))

        # 7. Kawasan sensitif
        if existing.in_protected_area or existing.touches_mangrove:
            what = []
            if existing.in_protected_area:
                what.append(t("c.kawasan_sensitif.protected", lang))
            if existing.touches_mangrove:
                what.append(t("c.kawasan_sensitif.mangrove", lang))
            components.append(ComponentImpact(
                key="kawasan_sensitif",
                name=t("c.kawasan_sensitif", lang),
                level="tinggi",
                score=100.0,
                summary=t("c.kawasan_sensitif.sum", lang, what=t("c.kawasan_sensitif.and", lang).join(what)),
                mitigation=[t("c.kawasan_sensitif.m1", lang)],
            ))

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
            lang=lang,
        )
        label = self.label(lang)
        if self.key == "lainnya" and str(p.get("nama_kegiatan", "")).strip():
            label = f"{label}: {p['nama_kegiatan'].strip()}"
        return AssessmentResult(
            scenario_key=self.key,
            scenario_label=label,
            params=dict(p),
            existing=existing.to_dict(),
            components=components,
            regulation=indicate_building_document(area, floor_total, existing, lang),
            assumptions=[
                t("a.storm", lang, storm=f(C.DESIGN_STORM_MM)),
                t("a.occupancy", lang, water=f(self.water_l_per_person(p)), waste=f(self.waste_kg_per_person(p), 1)),
                t("a.mangrove", lang),
                t("a.thresholds", lang),
                t("a.timeline", lang),
            ]
            + ([t("a.dummy", lang)] if existing.is_dummy else []),
            timeline=timeline,
        )


class PerumahanScenario(BuildingScenario):
    key = "perumahan"
    who = "penghuni"
    occupant_params = [
        Param("jumlah_unit", "int", 5, "unit"),
        Param("penghuni_per_unit", "float", C.DEFAULT_PERSONS_PER_UNIT, "orang"),
    ]

    def persons(self, p):
        return p["jumlah_unit"] * p["penghuni_per_unit"]


class RukoScenario(PerumahanScenario):
    key = "ruko"


class KantorScenario(BuildingScenario):
    key = "kantor"
    who = "karyawan"
    occupant_params = [Param("jumlah_karyawan", "int", 100, "orang")]

    def persons(self, p):
        return p["jumlah_karyawan"]


class HotelScenario(BuildingScenario):
    key = "hotel"
    who = "tamu"
    occupant_params = [Param("jumlah_kamar", "int", 50, "kamar")]

    def persons(self, p):
        return p["jumlah_kamar"] * C.HOTEL_GUESTS_PER_ROOM


class MalScenario(BuildingScenario):
    key = "mal"
    who = "pengunjung"
    occupant_params = [Param("pengunjung_per_hari", "int", 2000, "orang")]

    def persons(self, p):
        return p["pengunjung_per_hari"]


class LainnyaScenario(BuildingScenario):
    key = "lainnya"
    who = "orang"
    occupant_params = [
        Param("nama_kegiatan", "text", ""),
        Param("jumlah_orang", "int", 100, "orang"),
        Param("air_l_per_orang", "float", C.OCCUPANCY["lainnya"]["water_l"], "L"),
    ]

    def persons(self, p):
        return p["jumlah_orang"]

    def water_l_per_person(self, p):
        return float(p.get("air_l_per_orang") or C.OCCUPANCY["lainnya"]["water_l"])


PERIODS = [("konstruksi", 0), ("1th", 1), ("5th", 5), ("10th", 10)]


def build_timeline(components, construction_months, sediment_t, extra_runoff_m3_year,
                   water_m3_day, wastewater_m3_day, waste_kg_day, co2_t, lang="id") -> list:
    """Akumulasi dampak per periode: saat konstruksi, lalu 1/5/10 tahun setelah bangunan dipakai.

    Indeks risiko periode = rata-rata skor kontinu (0-100) komponen yang aktif di fase itu.
    Dampak permanen (limpasan dari permukaan kedap, hilangnya karbon) ikut dihitung di semua periode.
    Dampak yang menumpuk (air, limbah, sampah, limpasan) dijumlahkan sepanjang waktu.
    """
    def index(phase):
        active = [c for c in components if c.phase in (phase, "semua")]
        return round(sum(c.score for c in active) / len(active)) if active else 0

    out = []
    for key, years in PERIODS:
        days = 365 * years
        out.append({
            "key": key,
            "label": t(f"period.{key}", lang),
            "tahun": round(construction_months / 12, 2) if years == 0 else years,
            "indeks_risiko": index("konstruksi" if years == 0 else "operasional"),
            "sedimen_ton": sediment_t,
            "karbon_tco2": co2_t,
            "limpasan_tambahan_m3": extra_runoff_m3_year * years,
            "air_bersih_m3": water_m3_day * days,
            "air_limbah_m3": wastewater_m3_day * days,
            "sampah_ton": waste_kg_day * days / 1000,
        })
    return out
