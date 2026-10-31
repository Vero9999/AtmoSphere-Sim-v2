from atmosphere.llm import GemmaClient, coerce, compact_context, guess_scenario, rule_based_extract
from atmosphere.scenarios import SCENARIOS
from tests.test_scenarios import make_existing


def test_rule_based_extract_indonesian():
    text = (
        "Saya mau bangun 20 unit ruko 3 lantai di lahan 4.000 m², tapaknya sekitar 2.400 m² "
        "dan jalan/parkir 800 m². Lahannya berbukit jadi perlu cut and fill. Konstruksi 12 bulan."
    )
    out = rule_based_extract(text)
    assert out["luas_lahan_m2"] == 4000
    assert out["luas_tapak_bangunan_m2"] == 2400
    assert out["luas_perkerasan_m2"] == 800
    assert out["jumlah_unit"] == 20
    assert out["jumlah_lantai"] == 3
    assert out["durasi_konstruksi_bulan"] == 12
    assert out["cut_and_fill"] is True


def test_rule_based_extract_english():
    text = "An 8-storey hotel with 120 rooms on 5,000 m² of land, footprint 2,000 m², parking 1,500 m². 24 months."
    out = rule_based_extract(text)
    assert out["luas_lahan_m2"] == 5000
    assert out["jumlah_kamar"] == 120
    assert out["jumlah_lantai"] == 8
    assert out["luas_perkerasan_m2"] == 1500
    assert out["durasi_konstruksi_bulan"] == 24


def test_guess_scenario():
    assert guess_scenario("hotel 120 kamar") == "hotel"
    assert guess_scenario("gedung kantor untuk 300 karyawan") == "kantor"
    assert guess_scenario("20 unit ruko") == "ruko"
    assert guess_scenario("a shopping mall") == "mal"
    assert guess_scenario("sekolah untuk 600 siswa") == "lainnya"


def test_mock_client_works_in_both_languages(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "mock")
    llm = GemmaClient()
    assert llm.is_mock
    out = llm.extract_params("Sekolah 3 lantai untuk 600 siswa di lahan 8.000 m2", SCENARIOS["lainnya"])
    assert out["jumlah_orang"] == 600 and out["jenis_kegiatan"] == "lainnya"
    sc = SCENARIOS["ruko"]
    for lang, word in [("id", "Tingkat dampak"), ("en", "Overall impact")]:
        r = sc.run(make_existing(), sc.defaults(4000), lang=lang).to_dict()
        text = "".join(llm.explain_stream(r, lang))
        assert word in text
        assert "".join(llm.answer_stream("?", r, lang=lang))


def test_compact_context_is_smaller():
    import json
    sc = SCENARIOS["hotel"]
    r = sc.run(make_existing(), sc.defaults(4000)).to_dict()
    assert len(json.dumps(compact_context(r), default=str)) < len(json.dumps(r, default=str))


def test_coerce_cleans_llm_values():
    assert coerce(None, "float") is None
    assert coerce("", "int") is None
    assert coerce("4.000", "float") == 4000
    assert coerce(2.6, "int") == 3
    assert coerce("yes", "bool") is True
    assert coerce("abc", "float") is None
    assert coerce(-5, "float") is None
    assert coerce(" Sekolah ", "text") == "Sekolah"
