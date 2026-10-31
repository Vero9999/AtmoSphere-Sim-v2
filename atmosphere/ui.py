"""Komponen tampilan (HTML/SVG) untuk app.py, memakai palet moodboard "Prediksi Alam".

Semua angka yang ditampilkan berasal dari hasil model; modul ini hanya mengatur tampilan.
"""

import base64
import math
from html import escape

from . import config as C
from .i18n import fmt, t

# Palet moodboard (lihat docs/DESIGN.md)
MAROON = "#6E1529"
SAGE = "#8FAE92"
OLIVE = "#5F6F4A"
MUSTARD = "#E3AE57"
TAN = "#C3A784"
PAGE_BG = "#F6F3EC"
INK = "#1F2420"
MUTED = "#5B6158"
LINE = "#E4DED2"

LEVEL_COLOR = {"rendah": "#4F7A55", "sedang": "#B7791F", "tinggi": MAROON}
LEVEL_BG = {"rendah": "#E3EDE2", "sedang": "#F8EBD3", "tinggi": "#F3DDE1"}
ICONS = {
    "limpasan": "💧", "erosi": "⛰️", "air_bersih": "🚰", "air_limbah": "🧪",
    "sampah": "🗑️", "karbon": "🌳", "kawasan_sensitif": "🛡️",
}

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, .stApp, button, input, textarea {{ font-family: 'Plus Jakarta Sans', sans-serif; }}
.stApp {{ background: {PAGE_BG}; }}
.block-container {{ padding-top: 3.2rem; max-width: 1200px; }}
header[data-testid="stHeader"] {{ background: transparent; }}
h1, h2, h3, h4 {{ color: {INK}; letter-spacing: -0.01em; }}

.hero {{ background: linear-gradient(120deg, {OLIVE} 0%, #4B5A3A 55%, {MAROON} 130%);
  color: #fff; border-radius: 22px; padding: 24px 28px; margin-bottom: 16px; position: relative; overflow: hidden; }}
.hero:after {{ content: ""; position: absolute; right: -50px; top: -70px; width: 230px; height: 230px;
  border-radius: 50%; background: rgba(227,174,87,.22); }}
.hero h1 {{ color: #fff; font-size: 1.9rem; font-weight: 800; margin: 0 0 4px 0; padding: 0; }}
.hero p {{ margin: 0; opacity: .93; font-size: 1rem; max-width: 760px; }}
.chips {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }}
.chip {{ background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.35); color: #fff;
  padding: 4px 12px; border-radius: 999px; font-size: .78rem; font-weight: 600; }}
.chip.warn {{ background: {MUSTARD}; color: #3D2A06; border-color: {MUSTARD}; }}

.stepper {{ display: flex; gap: 8px; margin: 2px 0 18px 0; }}
.step {{ flex: 1; display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 14px;
  background: #EDE8DD; color: {MUTED}; font-weight: 600; font-size: .85rem; }}
.step .num {{ width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center;
  background: {TAN}; color: #fff; font-size: .8rem; flex: none; }}
.step.done {{ background: #E3EDE2; color: #2F4A33; }}
.step.done .num {{ background: {OLIVE}; }}
.step.active {{ background: #fff; color: {MAROON}; box-shadow: inset 0 0 0 2px {MAROON}; }}
.step.active .num {{ background: {MAROON}; }}

.section-title {{ display: flex; align-items: center; gap: 10px; margin: 26px 0 8px 0; }}
.section-title .badge {{ background: {MAROON}; color: #fff; width: 32px; height: 32px;
  border-radius: 10px; display: grid; place-items: center; font-weight: 800; }}
.section-title h2 {{ margin: 0; padding: 0; font-size: 1.35rem; font-weight: 800; }}
.section-sub {{ color: {MUTED}; margin: -2px 0 12px 42px; font-size: .92rem; }}

.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }}
.stat {{ background: #fff; border: 1px solid {LINE}; border-radius: 16px; padding: 14px 16px;
  display: flex; gap: 12px; align-items: center; }}
.stat .ic {{ width: 40px; height: 40px; border-radius: 12px; display: grid; place-items: center; font-size: 1.2rem;
  background: #EEF3EC; flex: none; }}
.stat .lb {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .05em; color: {MUTED}; font-weight: 700; }}
.stat .vl {{ font-size: 1.12rem; font-weight: 800; color: {INK}; }}

.alert {{ border-radius: 14px; padding: 12px 16px; margin-top: 10px; font-weight: 600; font-size: .92rem;
  background: #F3DDE1; color: {MAROON}; border-left: 6px solid {MAROON}; }}

.cover {{ display: flex; height: 16px; border-radius: 999px; overflow: hidden; margin: 6px 0 8px 0; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .82rem; color: #3A3F37; }}
.legend i {{ display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; }}

.panel {{ background: #fff; border: 1px solid {LINE}; border-radius: 20px; padding: 18px 20px; height: 100%; }}
.panel h4 {{ margin: 0 0 2px 0; font-size: 1rem; font-weight: 800; color: {INK}; }}
.muted {{ color: {MUTED}; font-size: .8rem; }}

.cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 14px; }}
.card {{ background: #fff; border: 1px solid {LINE}; border-radius: 18px; padding: 16px 18px;
  border-top: 5px solid var(--lv); }}
.card .top {{ display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
.card .ttl {{ display: flex; align-items: center; gap: 10px; font-weight: 700; color: {INK}; font-size: .92rem; }}
.card .ic {{ width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; background: var(--lvbg); flex: none; }}
.pill {{ font-size: .72rem; font-weight: 800; padding: 3px 10px; border-radius: 999px; color: var(--lv); background: var(--lvbg); white-space: nowrap; }}
.card .big {{ font-size: 1.45rem; font-weight: 800; color: var(--lv); margin-top: 10px; }}
.card .unit {{ font-size: .78rem; color: {MUTED}; font-weight: 600; }}
.card .delta {{ font-size: .8rem; color: {MUTED}; margin-top: 2px; }}
.card .sum {{ font-size: .85rem; color: #3A3F37; margin-top: 8px; line-height: 1.45; }}
.card details {{ margin-top: 8px; font-size: .84rem; }}
.card summary {{ cursor: pointer; color: {OLIVE}; font-weight: 700; }}
.card ul {{ margin: 6px 0 0 0; padding-left: 18px; color: #3A3F37; }}
.phase {{ font-size: .68rem; font-weight: 700; color: {OLIVE}; background: #EEF3EC; padding: 2px 8px; border-radius: 6px; }}

.pbars {{ display: flex; gap: 14px; align-items: flex-end; height: 150px; margin-top: 12px; }}
.pbar {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }}
.pbar .v {{ font-weight: 800; font-size: .95rem; color: {INK}; margin-bottom: 4px; }}
.pbar .b {{ width: 100%; max-width: 70px; border-radius: 10px 10px 4px 4px; }}
.pbar .l {{ font-size: .75rem; color: {MUTED}; margin-top: 6px; font-weight: 600; text-align: center; }}
.pbar.on .l {{ color: {MAROON}; font-weight: 800; }}

.doc {{ background: #fff; border: 1px solid {LINE}; border-left: 6px solid {MUSTARD}; border-radius: 18px; padding: 16px 22px; }}
.doc .t {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 800; color: #8A5A12; }}
.doc .d {{ font-size: 1.6rem; font-weight: 800; color: {INK}; }}
.doc ul {{ margin: 6px 0 4px 0; padding-left: 18px; color: #3A3F37; font-size: .9rem; }}
.doc .n {{ font-size: .78rem; color: {MUTED}; }}
.gemma-tag {{ display: inline-block; background: {OLIVE}; color: #fff; font-size: .72rem; font-weight: 800;
  padding: 3px 10px; border-radius: 8px; }}

div[data-testid="stForm"] {{ border-radius: 18px; border-color: {LINE}; background: #FFFDF8; }}
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button {{ border-radius: 12px; font-weight: 700; }}
section[data-testid="stSidebar"] {{ background: #EFEADF; }}
@media (max-width: 640px) {{
  .stepper {{ display: grid; grid-template-columns: 1fr 1fr; }}
  .hero {{ padding: 18px; }} .hero h1 {{ font-size: 1.5rem; }}
  .section-sub {{ margin-left: 0; }}
  .pbars {{ gap: 6px; }}
}}
iframe {{ border-radius: 18px; }}
</style>
"""


def _svg(svg: str, style: str = "width:100%") -> str:
    """Streamlit menyaring <svg> di st.html, jadi SVG dikirim sebagai gambar data URI."""
    data = base64.b64encode(svg.strip().encode("utf-8")).decode()
    return f'<img alt="" style="{style}" src="data:image/svg+xml;base64,{data}">'


def level_label(level: str, lang: str) -> str:
    return t(f"level.{level}", lang)


def hero(lang: str, llm_label: str, is_mock: bool, is_dummy: bool) -> str:
    chips = [f'<span class="chip">🤖 {escape(llm_label)}</span>', f'<span class="chip">📍 {t("app.city", lang)}</span>']
    if is_mock:
        chips.append(f'<span class="chip warn">{t("app.demo_chip", lang)}</span>')
    if is_dummy:
        chips.append(f'<span class="chip warn">⚠️ {t("app.dummy_chip", lang)}</span>')
    return (
        f'<div class="hero"><h1>🌏 AtmoSphere Sim</h1><p>{escape(t("app.tagline", lang))}</p>'
        f'<div class="chips">{"".join(chips)}</div></div>'
    )


def stepper(current: int, lang: str) -> str:
    out = []
    for i in range(1, 5):
        state = "done" if i < current else "active" if i == current else ""
        num = "✓" if i < current else str(i)
        out.append(f'<div class="step {state}"><span class="num">{num}</span>{escape(t(f"step.{i}", lang))}</div>')
    return f'<div class="stepper">{"".join(out)}</div>'


def section(num: int, title: str, sub: str = "") -> str:
    s = f'<div class="section-title"><span class="badge">{num}</span><h2>{escape(title)}</h2></div>'
    if sub:
        s += f'<div class="section-sub">{escape(sub)}</div>'
    return s


def stats(items: list) -> str:
    """items: [(ikon, label, nilai)]"""
    cells = "".join(
        f'<div class="stat"><div class="ic">{ic}</div><div><div class="lb">{escape(lb)}</div>'
        f'<div class="vl">{escape(vl)}</div></div></div>'
        for ic, lb, vl in items
    )
    return f'<div class="stats">{cells}</div>'


def cover_bar(shares: dict, lang: str) -> str:
    items = sorted(((k, v) for k, v in shares.items() if v > 0), key=lambda kv: -kv[1])
    color = C.LAND_COVER_COLORS
    segs = "".join(
        f'<span style="width:{v * 100:.1f}%;background:{color.get(k, "#999")}" title="{escape(t("lc." + k, lang))}"></span>'
        for k, v in items
    )
    legend = "".join(
        f'<span><i style="background:{color.get(k, "#999")}"></i>{escape(t("lc." + k, lang))} {v:.0%}</span>'
        for k, v in items
    )
    return f'<div class="cover">{segs}</div><div class="legend">{legend}</div>'


def level_of_index(index: int) -> str:
    return "rendah" if index < 34 else "sedang" if index < 67 else "tinggi"


def gauge(index: int, overall: str, lang: str) -> str:
    level = level_of_index(index)
    color = LEVEL_COLOR[level]
    r, cx, cy = 80, 100, 100
    length = math.pi * r
    filled = length * index / 100
    arc = f"M {cx - r} {cy} A {r} {r} 0 0 1 {cx + r} {cy}"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 120" font-family="sans-serif">
    <defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{SAGE}"/>
      <stop offset=".5" stop-color="{MUSTARD}"/><stop offset="1" stop-color="{MAROON}"/></linearGradient></defs>
    <path d="{arc}" fill="none" stroke="{LINE}" stroke-width="16" stroke-linecap="round"/>
    <path d="{arc}" fill="none" stroke="url(#g)" stroke-width="16" stroke-linecap="round"
      stroke-dasharray="{filled:.1f} {length:.1f}"/>
    <text x="100" y="92" text-anchor="middle" font-size="38" font-weight="800" fill="{color}">{index}</text>
    <text x="100" y="112" text-anchor="middle" font-size="11" fill="{MUTED}">{escape(t("s4.of100", lang))}</text>
  </svg>"""
    ov = LEVEL_COLOR[overall]
    return f"""
<div class="panel" style="text-align:center">
  <h4>{escape(t("s4.index", lang))}</h4>
  <div class="muted">{escape(t("s4.index_sub", lang))}</div>
  {_svg(svg, "width:100%;max-width:260px;margin-top:6px")}
  <div><span class="pill" style="--lv:{ov};--lvbg:{LEVEL_BG[overall]}">{escape(t("s4.overall", lang, v=level_label(overall, lang)))}</span></div>
</div>"""


def period_bars(timeline: list, active_key: str, lang: str) -> str:
    bars = ""
    for p in timeline:
        idx = p["indeks_risiko"]
        color = LEVEL_COLOR[level_of_index(idx)]
        on = " on" if p["key"] == active_key else ""
        outline = f"box-shadow:0 0 0 3px {INK};" if on else ""
        bars += (f'<div class="pbar{on}"><div class="v">{idx}</div>'
                 f'<div class="b" style="height:{max(idx, 4) * 0.95:.0f}px;background:{color};{outline}"></div>'
                 f'<div class="l">{escape(t("period." + p["key"], lang))}</div></div>')
    return (f'<div class="panel"><h4>{escape(t("s4.by_period", lang))}</h4>'
            f'<div class="muted">{escape(t("s4.by_period_sub", lang))}</div><div class="pbars">{bars}</div></div>')


def period_totals(p: dict, lang: str) -> str:
    f = lambda x: fmt(x, 0, lang)  # noqa: E731
    items = [
        ("⛰️", t("s4.t_sed", lang), f"{f(p['sedimen_ton'])} t"),
        ("🌳", t("s4.t_co2", lang), f"{f(p['karbon_tco2'])} t"),
        ("💧", t("s4.t_runoff", lang), f"{f(p['limpasan_tambahan_m3'])} m³"),
        ("🚰", t("s4.t_water", lang), f"{f(p['air_bersih_m3'])} m³"),
        ("🧪", t("s4.t_ww", lang), f"{f(p['air_limbah_m3'])} m³"),
        ("🗑️", t("s4.t_waste", lang), f"{f(p['sampah_ton'])} t"),
    ]
    return stats(items)


def component_cards(components: list, lang: str) -> str:
    cards = ""
    for c in components:
        lv, bg = LEVEL_COLOR[c.level], LEVEL_BG[c.level]
        big = ""
        if c.after is not None:
            d = 1 if abs(c.after) < 100 else 0
            big = f'<div class="big">{fmt(c.after, d, lang)} <span class="unit">{escape(c.unit)}</span></div>'
            if c.before is not None:
                big += f'<div class="delta">{escape(t("s4.now", lang, v=fmt(c.before, d, lang)))}</div>'
        mit = ""
        if c.mitigation:
            items = "".join(f"<li>{escape(m)}</li>" for m in c.mitigation)
            mit = (f"<details><summary>{escape(t('s4.mitigation', lang, n=len(c.mitigation)))}</summary>"
                   f"<ul>{items}</ul></details>")
        cards += f"""
<div class="card" style="--lv:{lv};--lvbg:{bg}">
  <div class="top"><div class="ttl"><span class="ic">{ICONS.get(c.key, "•")}</span>{escape(c.name)}</div>
    <span class="pill">{escape(level_label(c.level, lang))}</span></div>
  <div style="margin-top:8px"><span class="phase">{escape(t("phase." + c.phase, lang))}</span></div>
  {big}<div class="sum">{escape(c.summary)}</div>{mit}
</div>"""
    return f'<div class="cards">{cards}</div>'


def regulation_box(reg: dict, lang: str) -> str:
    reasons = "".join(f"<li>{escape(r)}</li>" for r in reg.get("alasan", []))
    return (
        f'<div class="doc"><div class="t">📄 {escape(t("s4.doc", lang))}</div>'
        f'<div class="d">{escape(reg.get("dokumen", "-"))}</div><ul>{reasons}</ul>'
        f'<div class="n">{escape(reg.get("catatan", ""))}</div></div>'
    )


def components_for_period(components: list, period_key: str) -> list:
    phase = "konstruksi" if period_key == "konstruksi" else "operasional"
    return [c for c in components if c.phase in (phase, "semua")]
