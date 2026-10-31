import pytest

from atmosphere import models as M
from atmosphere.results import AssessmentResult, ComponentImpact


def test_scs_runoff_known_value():
    # CN 70, P 100 mm -> S = 108.86, Ia = 21.77, Q ≈ 32.7 mm
    assert M.scs_runoff_mm(100, 70) == pytest.approx(32.7, abs=0.2)


def test_scs_runoff_zero_below_initial_abstraction():
    assert M.scs_runoff_mm(5, 60) == 0


def test_runoff_increases_with_impervious():
    assert M.scs_runoff_mm(100, 98) > M.scs_runoff_mm(100, 70)


def test_composite_cn_is_area_weighted():
    # hutan C = 70, kedap_air C = 98 -> 84
    assert M.composite_cn({"hutan": 0.5, "kedap_air": 0.5}, "C") == pytest.approx(84)


def test_erosion_classes_and_levels():
    assert M.erosion_class(10) == "sangat ringan"
    assert M.erosion_class(100) == "sedang"
    assert M.erosion_class(1000) == "sangat berat"
    assert M.erosion_level(10) == "rendah"
    assert M.erosion_level(1000) == "tinggi"


def test_bare_land_erodes_more_than_forest():
    r = M.rainfall_erosivity(2500)
    ls = M.ls_factor(15)
    assert M.usle(r, 0.25, ls, 1.0) > M.usle(r, 0.25, ls, 0.001)


def test_carbon_water_waste():
    assert M.carbon_stock_t({"hutan": 1.0}, 2) == pytest.approx(240)
    assert M.water_demand_m3_day(100) == pytest.approx(15)
    assert M.waste_kg_day(100) == pytest.approx(70)


def test_level_thresholds():
    assert M.level_from_thresholds(5, "limpasan_kenaikan_pct") == "rendah"
    assert M.level_from_thresholds(30, "limpasan_kenaikan_pct") == "sedang"
    assert M.level_from_thresholds(90, "limpasan_kenaikan_pct") == "tinggi"


def test_overall_level_is_worst_component():
    comps = [
        ComponentImpact("a", "A", "rendah", ""),
        ComponentImpact("b", "B", "tinggi", ""),
        ComponentImpact("c", "C", "sedang", ""),
    ]
    r = AssessmentResult("x", "X", {}, {}, comps, {})
    assert r.overall_level == "tinggi"
    assert r.to_dict()["tingkat_dampak_keseluruhan"] == "tinggi"
