import pytest

from atmosphere.data import ExistingCondition
from atmosphere.scenarios import SCENARIOS


def make_existing(**overrides):
    base = dict(
        area_m2=4000,
        land_cover_share={"hutan": 0.5, "semak": 0.5},
        slope_pct=15,
        hsg="C",
        soil_k=0.25,
        rainfall_mm_year=2500,
        population_density=100,
        pm25_ugm3=15,
        in_protected_area=False,
        touches_mangrove=False,
        covered_fraction=1.0,
        is_dummy=True,
        data_date="2026-10-25",
    )
    base.update(overrides)
    return ExistingCondition(**base)


@pytest.fixture
def sc():
    return SCENARIOS["perumahan"]


def test_registry_has_separate_types_and_coming_soon():
    for key in ["perumahan", "ruko", "kantor", "hotel", "mal", "lainnya"]:
        assert SCENARIOS[key].available
    assert not SCENARIOS["industri"].available
    assert not SCENARIOS["reklamasi"].available


def test_defaults_scale_with_area(sc):
    d = sc.defaults(4000)
    assert d["luas_lahan_m2"] == 4000
    assert d["luas_tapak_bangunan_m2"] == 2400


def test_housing_runs_and_flags_cut_and_fill(sc):
    params = sc.defaults(4000) | {"cut_and_fill": True, "jumlah_unit": 20}
    result = sc.run(make_existing(), params)
    by_key = {c.key: c for c in result.components}
    assert set(by_key) == {"limpasan", "erosi", "air_bersih", "air_limbah", "sampah", "karbon"}
    assert by_key["limpasan"].after > by_key["limpasan"].before
    assert by_key["erosi"].level == "tinggi"
    assert result.regulation["dokumen"] in {"AMDAL", "UKL-UPL", "SPPL"}


def test_mitigation_lowers_impact(sc):
    base = sc.defaults(4000) | {"cut_and_fill": True}
    plain = {c.key: c for c in sc.run(make_existing(), base).components}
    better = {c.key: c for c in sc.run(
        make_existing(), base | {"pengendali_erosi": True, "sumur_resapan_m3": 200}).components}
    assert better["erosi"].after < plain["erosi"].after
    assert better["limpasan"].after < plain["limpasan"].after


def test_sensitive_area_requires_amdal(sc):
    result = sc.run(make_existing(touches_mangrove=True), sc.defaults(1000))
    assert "kawasan_sensitif" in {c.key for c in result.components}
    assert result.regulation["dokumen"] == "AMDAL"
    assert result.overall_level == "tinggi"


def test_timeline_accumulates_over_years(sc):
    params = sc.defaults(4000) | {"jumlah_unit": 20}
    tl = sc.run(make_existing(), params).timeline
    assert [t["key"] for t in tl] == ["konstruksi", "1th", "5th", "10th"]
    assert tl[0]["air_bersih_m3"] == 0
    # 20 unit x 4 orang x 150 L = 12 m3/hari -> 1 tahun = 4.380 m3
    assert tl[1]["air_bersih_m3"] == pytest.approx(4380)
    assert tl[3]["sampah_ton"] == pytest.approx(10 * tl[1]["sampah_ton"])
    assert tl[2]["limpasan_tambahan_m3"] > tl[1]["limpasan_tambahan_m3"] > 0
    assert all(0 <= t["indeks_risiko"] <= 100 for t in tl)


def test_result_serializes(sc):
    d = sc.run(make_existing(), sc.defaults(2000)).to_dict()
    assert d["timeline"] and d["components"][0]["phase"]


def persons_from(result):
    water = next(c for c in result.components if c.key == "air_bersih")
    return water.after


@pytest.mark.parametrize("key, extra, water_m3", [
    ("kantor", {"jumlah_karyawan": 300}, 15.0),      # 300 x 50 L
    ("hotel", {"jumlah_kamar": 100}, 50.0),          # 100 x 2 tamu x 250 L
    ("mal", {"pengunjung_per_hari": 5000}, 50.0),    # 5000 x 10 L
    ("lainnya", {"jumlah_orang": 600, "air_l_per_orang": 50, "nama_kegiatan": "Sekolah"}, 30.0),
])
def test_building_types_use_their_own_occupancy(key, extra, water_m3):
    sc = SCENARIOS[key]
    result = sc.run(make_existing(), sc.defaults(4000) | extra)
    assert persons_from(result) == pytest.approx(water_m3)
    assert len(result.components) == 6


def test_other_uses_custom_name():
    sc = SCENARIOS["lainnya"]
    result = sc.run(make_existing(), sc.defaults(2000) | {"nama_kegiatan": "Sekolah"})
    assert result.scenario_label.endswith("Sekolah")


def test_english_output():
    sc = SCENARIOS["ruko"]
    result = sc.run(make_existing(touches_mangrove=True), sc.defaults(4000), lang="en")
    names = [c.name for c in result.components]
    assert "Stormwater runoff (flood risk)" in names
    assert "mangrove" in result.regulation["alasan"][0]
    assert result.timeline[1]["label"] == "1 year"
    assert sc.label("en") == "Shophouse (ruko)"


def test_every_text_has_both_languages():
    from atmosphere.i18n import TEXT
    assert set(TEXT["id"]) == set(TEXT["en"])


def test_operational_index_not_zero_after_heavy_construction():
    # Gudang di lahan yang sudah industri: dulu indeks 50 lalu 0 di tahun 1-10.
    sc = SCENARIOS["lainnya"]
    ex = make_existing(land_cover_share={"industri": 0.6, "lahan_terbuka": 0.4})
    tl = sc.run(ex, sc.defaults(20000) | {"jumlah_orang": 150, "cut_and_fill": True}).timeline
    assert tl[0]["indeks_risiko"] > tl[1]["indeks_risiko"] > 0


def test_scores_match_levels():
    sc = SCENARIOS["ruko"]
    for c in sc.run(make_existing(touches_mangrove=True), sc.defaults(4000) | {"cut_and_fill": True}).components:
        band = "rendah" if c.score < 33 else "sedang" if c.score < 67 else "tinggi"
        assert band == c.level, (c.key, c.score, c.level)
