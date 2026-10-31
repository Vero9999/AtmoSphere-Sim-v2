"""Uji alur halaman lewat Streamlit AppTest (mode demo, tanpa Gemma)."""

import pytest
from shapely.geometry import mapping

from atmosphere.geo import BATAM_CENTER, square_around

streamlit_testing = pytest.importorskip("streamlit.testing.v1")


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "mock")
    import atmosphere.geo
    monkeypatch.setattr(atmosphere.geo, "reverse_geocode", lambda lat, lon, lang="id": "Jalan Uji, Batam Kota")
    at = streamlit_testing.AppTest.from_file("../app.py", default_timeout=60)
    at.run()
    assert not at.exception
    return at


def area_geojson(dlon=0.0):
    lat, lon = BATAM_CENTER
    return mapping(square_around(lon + dlon, lat, 4000))


def button(at, label_start):
    return next(b for b in at.button if b.label.startswith(label_start))


def test_full_flow_two_plans_and_language(app):
    at = app
    at.session_state["area"] = area_geojson()
    at.run()
    assert not at.exception
    assert any("Kondisi lingkungan" in m.value for m in at.markdown) or at.radio

    # Pilih Ruko, isi dengan Gemma (mode demo = ekstraksi pola), lalu prediksi
    at.radio(key="scenario_key").set_value("ruko").run()
    at.text_area(key="plan_text").input("20 unit ruko 3 lantai di lahan 4.000 m², parkir 800 m², 12 bulan").run()
    button(at, "✨").click().run()
    assert not at.exception
    assert at.session_state["w_jumlah_unit"] == 20
    button(at, "🔍").click().run()
    assert not at.exception
    assert at.session_state["run"]["scenario_key"] == "ruko"

    # Simpan rencana 1, buat rencana baru
    button(at, "💾").click().run()
    assert len(at.session_state["plans"]) == 1
    button(at, "➕").click().run()
    assert at.session_state["area"] is None

    # Rencana 2: hotel di lokasi lain, Gemma (demo) mendeteksi jenis kegiatan
    at.session_state["area"] = area_geojson(0.01)
    at.run()
    at.text_area(key="plan_text").input("Hotel 8 lantai dengan 120 kamar di lahan 5.000 m2").run()
    button(at, "✨").click().run()
    assert at.session_state["scenario_key"] == "hotel"
    assert at.session_state["w_jumlah_kamar"] == 120
    button(at, "🔍").click().run()
    button(at, "💾").click().run()
    assert not at.exception
    assert len(at.session_state["plans"]) == 2
    assert len(at.dataframe) == 1  # tabel perbandingan

    # Ganti bahasa ke Inggris
    at.session_state["lang_widget"] = "en"
    at.run()
    assert not at.exception
    assert button(at, "💾").label == "💾 Save plan"


def test_location_lock_and_thousand_separators(app):
    at = app
    at.session_state["area"] = area_geojson()
    at.session_state["address"] = "Jalan Uji, Batam Kota"
    at.run()
    assert not at.exception
    assert any(b.label.startswith("🗺️") for b in at.button)  # tombol Ubah lokasi = lokasi terkunci
    import re
    assert re.fullmatch(r"\d\.\d{3}", at.session_state["w_luas_lahan_m2"])  # mis. "3.973"
    at.text_input(key="w_luas_lahan_m2").input("1.250.000")
    next(b for b in at.button if b.label.startswith("🔍")).click().run()
    assert not at.exception
    assert at.session_state["run"]["params"]["luas_lahan_m2"] == 1_250_000
