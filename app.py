"""AtmoSphere Sim — aplikasi web Streamlit.

Jalankan:  streamlit run app.py
"""

import dataclasses
import os

import folium
import streamlit as st
from dotenv import load_dotenv
from folium.plugins import Draw
from shapely.geometry import mapping, shape
from streamlit_folium import st_folium

from atmosphere import config as C
from atmosphere import plans as P
from atmosphere import ui
from atmosphere.data import ExistingDataStore
from atmosphere.geo import BATAM_CENTER, area_m2, square_around
from atmosphere.i18n import LANGS, fmt, t
from atmosphere.llm import GemmaClient
from atmosphere.scenarios import SCENARIOS

load_dotenv()
st.set_page_config(page_title="AtmoSphere Sim", page_icon="🌏", layout="wide")

# Streamlit Community Cloud: rahasia diisi lewat st.secrets, bukan file .env
try:
    for _k in ("LLM_BACKEND", "GEMMA_MODEL", "GEMMA_THINKING", "GOOGLE_API_KEY", "OLLAMA_URL"):
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:  # tidak ada secrets.toml saat dijalankan lokal
    pass


@st.cache_resource
def get_store():
    return ExistingDataStore()


@st.cache_resource
def get_llm():
    return GemmaClient()


@st.cache_data
def map_layer(lang: str) -> dict:
    """GeoJSON tutupan lahan dengan label sesuai bahasa untuk tooltip peta."""
    gj = get_store().geojson
    feats = []
    for f in gj["features"]:
        props = dict(f["properties"])
        props["label"] = t("lc." + props["tutupan_lahan"], lang)
        props["lindung"] = ("✓" if props.get("kawasan_lindung") else "–")
        feats.append({"type": "Feature", "geometry": f["geometry"], "properties": props})
    return {"type": "FeatureCollection", "features": feats}


store, llm = get_store(), get_llm()
ss = st.session_state
for key, value in {
    "lang": "id", "area": None, "run": None, "vals": {}, "plans": [], "active_plan": None,
    "explanations": {}, "chats": {}, "photo_result": None, "fill_questions": None, "flash": None,
    "plan_seq": 1, "scenario_key": "perumahan",
}.items():
    ss.setdefault(key, value)

AVAILABLE = [k for k, s in SCENARIOS.items() if s.available]
FORM_KEYS = ("w_", "fix_")


def clear_form(keep_area: bool = False):
    for k in [k for k in ss.keys() if isinstance(k, str) and k.startswith(FORM_KEYS)]:
        del ss[k]
    ss.vals, ss.run, ss.photo_result, ss.fill_questions = {}, None, None, None
    if not keep_area:
        ss.area = None
    ss.pop("plan_text", None)


def set_area(geom: dict):
    clear_form()
    ss.area = geom
    st.rerun()


def new_plan():
    clear_form()
    ss.active_plan = None
    ss.pop("plan_name", None)


def open_plan(plan):
    clear_form()
    ss.area = plan.area
    ss.scenario_key = plan.scenario_key
    ss.vals = dict(plan.params)
    ss.run = {"scenario_key": plan.scenario_key, "params": dict(plan.params), "existing": plan.existing}
    ss.active_plan = plan.id
    ss.plan_name = plan.name


def delete_plan(plan_id):
    ss.plans = [p for p in ss.plans if p.id != plan_id]
    if ss.active_plan == plan_id:
        ss.active_plan = None


# --- Bahasa, header, sidebar ------------------------------------------------------
st.html(ui.CSS)
_, lang_col = st.columns([5, 1])
with lang_col:
    picked = st.segmented_control(
        "Bahasa / Language", list(LANGS), default=ss.lang, key="lang_widget",
        format_func=lambda k: {"id": "🇮🇩 ID", "en": "🇬🇧 EN"}[k], label_visibility="collapsed",
    )
    if picked and picked != ss.lang:
        ss.lang = picked
        st.rerun()
lang = ss.lang

step = 4 if ss.run else 3 if ss.area else 1
st.html(ui.hero(lang, llm.label, llm.is_mock, store.is_dummy))
st.html(ui.stepper(step, lang))
if llm.last_error:
    st.warning(llm.last_error)

with st.sidebar:
    st.markdown("### 🌏 AtmoSphere Sim")
    st.caption(t("side.about", lang))
    st.markdown(f"**{t('side.ai', lang)}:** {llm.label}")
    st.info(t("side.dummy", lang))
    st.markdown(f"**{t('plan.list', lang)}**")
    if not ss.plans:
        st.caption(t("plan.none", lang))
    for plan in ss.plans:
        c1, c2, c3 = st.columns([3, 1.2, 1.2])
        mark = "▶ " if plan.id == ss.active_plan else ""
        c1.markdown(f"{mark}**{plan.name}**  \n<small>{SCENARIOS[plan.scenario_key].label(lang)}</small>",
                    unsafe_allow_html=True)
        c2.button(t("plan.open", lang), key=f"open_{plan.id}", on_click=open_plan, args=(plan,))
        c3.button("🗑", key=f"del_{plan.id}", on_click=delete_plan, args=(plan.id,), help=t("plan.delete", lang))
    st.button(t("plan.new", lang), on_click=new_plan, use_container_width=True)
    st.markdown(f"**{t('side.legend', lang)}**")
    for k, color in C.LAND_COVER_COLORS.items():
        st.markdown(f"<span style='color:{color};font-size:1.1rem'>■</span> {t('lc.' + k, lang)}",
                    unsafe_allow_html=True)
    if st.button(t("side.reset", lang), use_container_width=True):
        for k in list(ss.keys()):
            del ss[k]
        st.rerun()


# --- 1. Lokasi --------------------------------------------------------------------
@st.fragment
def map_section():
    st.html(ui.section(1, t("s1.title", lang), t("s1.sub", lang)))
    col_map, col_opt = st.columns([3, 1])
    with col_opt:
        with st.container(border=True):
            st.markdown(f"**{t('s1.settings', lang)}**")
            show_layer = st.toggle(t("s1.layer", lang), value=True, key="show_layer")
            point_area = st.number_input(t("s1.point_area", lang), min_value=50.0, value=1000.0,
                                         step=100.0, key="point_area")
            st.caption(t("s1.basemap_hint", lang))

    with col_map:
        m = folium.Map(location=BATAM_CENTER, zoom_start=12, tiles=None)
        folium.TileLayer("OpenStreetMap", name=t("map.street", lang)).add_to(m)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics", name=t("map.sat", lang), show=False,
        ).add_to(m)
        if show_layer:
            folium.GeoJson(
                map_layer(lang), name=t("map.cover", lang),
                style_function=lambda f: {
                    "fillColor": C.LAND_COVER_COLORS.get(f["properties"]["tutupan_lahan"], "#999"),
                    "color": "none", "fillOpacity": 0.45,
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=["label", "kemiringan_pct", "lindung"],
                    aliases=[t("s2.cover", lang), t("map.slope", lang), t("map.protected", lang)],
                ),
            ).add_to(m)
        for plan in ss.plans:
            if plan.id != ss.active_plan:
                folium.GeoJson(
                    plan.area, tooltip=f"{t('s1.saved_area', lang)}: {plan.name}",
                    style_function=lambda f: {"color": ui.OLIVE, "weight": 3, "dashArray": "6 6",
                                              "fillColor": ui.SAGE, "fillOpacity": 0.15},
                ).add_to(m)
        if ss.area:
            folium.GeoJson(
                ss.area, name=t("s1.plan_area", lang), tooltip=t("s1.plan_area", lang),
                style_function=lambda f: {"color": ui.MAROON, "weight": 4, "fillColor": ui.MUSTARD,
                                          "fillOpacity": 0.25},
            ).add_to(m)
        Draw(
            export=False,
            draw_options={"polyline": False, "circle": False, "circlemarker": False, "marker": False},
            edit_options={"edit": False},
        ).add_to(m)
        folium.LayerControl(collapsed=True).add_to(m)
        out = st_folium(m, height=500, use_container_width=True, key="map",
                        returned_objects=["all_drawings", "last_clicked"])

    c1, c2 = st.columns(2)
    drawings = (out or {}).get("all_drawings") or []
    if c1.button(t("s1.use_drawn", lang), disabled=not drawings, type="primary", use_container_width=True):
        set_area(drawings[-1]["geometry"])
    clicked = (out or {}).get("last_clicked")
    if c2.button(t("s1.use_point", lang), disabled=not clicked, use_container_width=True):
        set_area(mapping(square_around(clicked["lng"], clicked["lat"], point_area)))


# --- 2. Kondisi eksisting ----------------------------------------------------------
def conditions_section(polygon):
    existing = store.query(polygon)
    if existing is None:
        st.error(t("s1.outside", lang))
        return None
    st.html(ui.section(2, t("s2.title", lang), t("s2.sub", lang, date=existing.data_date)))
    if existing.covered_fraction < 0.9:
        st.warning(t("s2.coverage", lang, pct=round(existing.covered_fraction * 100)))
    st.html(ui.stats([
        ("📐", t("s2.area", lang), f"{fmt(area_m2(polygon), 0, lang)} m²"),
        ("⛰️", t("s2.slope", lang), f"{fmt(existing.slope_pct, 1, lang)} %"),
        ("🌧️", t("s2.rain", lang), f"{fmt(existing.rainfall_mm_year, 0, lang)} {t('s2.rain_unit', lang)}"),
        ("🌫️", t("s2.pm25", lang), f"{fmt(existing.pm25_ugm3, 1, lang)} µg/m³"),
    ]))
    with st.container(border=True):
        st.markdown(f"**{t('s2.cover', lang)}**")
        st.html(ui.cover_bar(existing.land_cover_share, lang))
    if existing.in_protected_area:
        st.html(f'<div class="alert">{t("s2.alert_protected", lang)}</div>')
    if existing.touches_mangrove:
        st.html(f'<div class="alert">{t("s2.alert_mangrove", lang)}</div>')

    with st.expander(t("s2.validate", lang)):
        cover_keys = list(C.LAND_COVER_LABELS)
        choice = st.selectbox(t("s2.cover_fix", lang), ["-"] + cover_keys, key="fix_cover",
                              format_func=lambda k: t("s2.as_data", lang) if k == "-" else t("lc." + k, lang))
        ss.setdefault("fix_slope", min(60.0, float(round(existing.slope_pct, 1))))
        slope_fix = st.slider(t("s2.slope_fix", lang), 0.0, 60.0, key="fix_slope")
        photo = st.file_uploader(t("s2.photo", lang), type=["jpg", "jpeg", "png"], key="fix_photo")
        if photo and st.button(t("s2.photo_btn", lang)):
            with st.spinner(t("s2.photo_wait", lang)):
                ss.photo_result = llm.check_photo(photo.getvalue(), photo.type or "image/jpeg",
                                                  existing.to_dict(), lang)
        if ss.photo_result:
            st.markdown(ss.photo_result)

    corrections = []
    if choice != "-":
        existing = dataclasses.replace(existing, land_cover_share={choice: 1.0})
        corrections.append(t("s2.fix_cover", lang, v=t("lc." + choice, lang)))
    if abs(slope_fix - round(existing.slope_pct, 1)) > 0.05:
        existing = dataclasses.replace(existing, slope_pct=slope_fix)
        corrections.append(t("s2.fix_slope", lang, v=fmt(slope_fix, 1, lang)))
    existing.corrections = corrections
    return existing


# --- 3. Rencana --------------------------------------------------------------------
def widget_value(p, value):
    if p.kind == "bool":
        return bool(value)
    if p.kind == "text":
        return str(value or "")
    low = p.min_value or 0
    return max(int(round(float(value))), int(low)) if p.kind == "int" else max(float(value), float(low))


def plan_section(polygon, existing):
    st.html(ui.section(3, t("s3.title", lang), t("s3.sub", lang)))
    if ss.get("pending_scenario"):  # dari deteksi Gemma, diterapkan sebelum widget dibuat
        ss.scenario_key = ss.pop("pending_scenario")
    if ss.scenario_key not in AVAILABLE:
        ss.scenario_key = AVAILABLE[0]
    key = st.radio(t("s3.kind", lang), AVAILABLE, key="scenario_key", horizontal=True,
                   format_func=lambda k: SCENARIOS[k].label(lang))
    scenario = SCENARIOS[key]
    coming = [s.label(lang) for s in SCENARIOS.values() if not s.available]
    st.caption(f"{scenario.description(lang)} · {t('s3.coming', lang, v=', '.join(coming))}")

    defaults = scenario.defaults(area_m2(polygon))
    for p in scenario.params:
        ss.vals.setdefault(p.key, defaults[p.key])
        ss.setdefault(f"w_{p.key}", widget_value(p, ss.vals[p.key]))

    text = st.text_area(t("s3.text", lang), placeholder=scenario.example_text(lang), height=90, key="plan_text")
    if st.button(t("s3.fill", lang), type="primary"):
        if not text.strip():
            st.warning(t("s3.need_text", lang))
        else:
            with st.spinner(t("s3.fill_wait", lang)):
                extracted = llm.extract_params(text, scenario, lang)
            kind = extracted.pop("jenis_kegiatan", None)
            ss.fill_questions = extracted.pop("pertanyaan", None)
            target = scenario
            if kind and kind != key:
                ss.pending_scenario = kind
                ss.flash = t("s3.switched", lang, v=SCENARIOS[kind].label(lang))
                target = SCENARIOS[kind]
            by_key = {p.key: p for s in AVAILABLE for p in SCENARIOS[s].params}
            for k, v in extracted.items():
                ss.vals[k] = v
                ss[f"w_{k}"] = widget_value(by_key[k], v)
            for p in target.params:  # isi kunci baru jenis kegiatan yang terdeteksi
                ss.vals.setdefault(p.key, target.defaults(area_m2(polygon))[p.key])
            st.rerun()
    if ss.flash:
        st.success(ss.flash)
        ss.flash = None
    if ss.fill_questions:
        st.info(f"{t('s3.questions', lang)}\n\n" + "\n".join(f"- {q}" for q in ss.fill_questions))

    with st.form("params"):
        st.write(t("s3.check", lang))
        cols = st.columns(2)
        values = {}
        for i, p in enumerate(scenario.params):
            col = cols[i % 2]
            wkey = f"w_{p.key}"
            label, help_ = p.label(lang), p.help(lang)
            if p.kind == "bool":
                values[p.key] = col.checkbox(label, key=wkey, help=help_)
            elif p.kind == "text":
                values[p.key] = col.text_input(label, key=wkey, help=help_)
            elif p.kind == "int":
                values[p.key] = col.number_input(label, key=wkey, step=1, min_value=int(p.min_value or 0),
                                                 help=help_)
            else:
                values[p.key] = col.number_input(label, key=wkey, step=10.0,
                                                 min_value=float(p.min_value or 0), help=help_)
        submitted = st.form_submit_button(t("s3.predict", lang), type="primary")
    if submitted:
        ss.vals.update(values)
        ss.run = {"scenario_key": key, "params": dict(values), "existing": existing}
        st.rerun()


# --- 4. Hasil ----------------------------------------------------------------------
@st.fragment
def results_view(result):
    keys = [p["key"] for p in result.timeline]
    period = st.segmented_control(t("s4.period", lang), keys, default="konstruksi", key="period",
                                  format_func=lambda k: t("period." + k, lang)) or "konstruksi"
    p = next(x for x in result.timeline if x["key"] == period)
    c1, c2 = st.columns([1, 1.6])
    with c1:
        st.html(ui.gauge(p["indeks_risiko"], result.overall_level, lang))
    with c2:
        st.html(ui.period_bars(result.timeline, period, lang))
    st.markdown(f"#### {t('s4.totals', lang, v=t('period.' + period, lang))}")
    st.html(ui.period_totals(p, lang))
    head, toggle = st.columns([3, 1])
    head.markdown(f"#### {t('s4.cards', lang)}")
    show_all = toggle.toggle(t("s4.show_all", lang), key="show_all")
    comps = result.components if show_all else ui.components_for_period(result.components, period)
    st.html(ui.component_cards(comps, lang))


@st.fragment
def gemma_view(result_dict, sig):
    with st.container(border=True):
        st.html('<span class="gemma-tag">🤖 GEMMA 4</span>')
        st.markdown(f"#### {t('s4.ai_title', lang)}")
        cache_key = f"{sig}:{lang}"
        if cache_key in ss.explanations:
            st.markdown(ss.explanations[cache_key])
        elif st.button(t("s4.ai_btn", lang), type="primary"):
            text = st.write_stream(llm.explain_stream(result_dict, lang))
            ss.explanations[cache_key] = text if isinstance(text, str) else "".join(map(str, text))
            if llm.last_error:
                st.warning(llm.last_error)

        history = ss.chats.setdefault(cache_key, [])
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        question = st.chat_input(t("s4.ask", lang), key=f"chat_{cache_key}")
        st.caption(t("s4.ask_hint", lang))
        if question:
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                answer = st.write_stream(llm.answer_stream(question, result_dict, history, lang))
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer if isinstance(answer, str) else str(answer)})


def results_section():
    run = ss.run
    result = P.compute(run["scenario_key"], run["params"], run["existing"], lang)
    sig = P.signature(run["scenario_key"], run["params"], run["existing"])
    st.html(ui.section(4, t("s4.title", lang), t("s4.sub", lang, v=result.scenario_label)))
    results_view(result)
    st.write("")
    st.html(ui.regulation_box(result.regulation, lang))
    with st.expander(t("s4.assumptions", lang)):
        for a in result.assumptions:
            st.markdown(f"- {a}")
        if result.existing.get("koreksi_user"):
            st.markdown("- " + t("s4.user_fix", lang, v="; ".join(result.existing["koreksi_user"])))
    st.write("")
    gemma_view(result.to_dict(), sig)

    # Simpan rencana
    st.html(ui.section(5, t("plan.title", lang)))
    with st.container(border=True):
        active = next((p for p in ss.plans if p.id == ss.active_plan), None)
        ss.setdefault("plan_name", active.name if active else t("plan.default", lang, n=ss.plan_seq))
        c1, c2, c3 = st.columns([2, 1, 1], vertical_alignment="bottom")
        name = c1.text_input(t("plan.name", lang), key="plan_name")
        if c2.button(t("plan.save", lang), type="primary", use_container_width=True):
            name = name.strip() or t("plan.default", lang, n=ss.plan_seq)
            if active:
                active.name, active.scenario_key = name, run["scenario_key"]
                active.params, active.existing, active.area = dict(run["params"]), run["existing"], ss.area
                ss.save_msg = t("plan.updated", lang, v=name)
            else:
                plan = P.Plan(name, run["scenario_key"], dict(run["params"]), ss.area, run["existing"])
                ss.plans.append(plan)
                ss.active_plan = plan.id
                ss.plan_seq += 1
                ss.save_msg = t("plan.saved", lang, v=name)
            st.rerun()
        if ss.get("save_msg"):
            st.success(ss.pop("save_msg"))
        c3.button(t("plan.new", lang), on_click=new_plan, use_container_width=True, key="new_plan_main")


def compare_section():
    if not ss.plans:
        return
    st.markdown(f"### 📊 {t('plan.compare', lang)}")
    rows = P.comparison_rows(ss.plans, lang)
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.download_button(t("plan.excel", lang), data=P.to_excel(rows), file_name="atmosphere-sim-plans.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption(t("plan.session_note", lang))


# --- Alur halaman ------------------------------------------------------------------
def main_flow():
    map_section()
    if not ss.area:
        return
    polygon = shape(ss.area)
    existing = conditions_section(polygon)
    if existing is None:
        return
    plan_section(polygon, existing)
    if ss.run:
        results_section()


main_flow()
compare_section()
