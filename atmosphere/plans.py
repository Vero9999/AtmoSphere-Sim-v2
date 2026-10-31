"""Simpan beberapa rencana dalam satu sesi, bandingkan, dan ekspor ke Excel.

Rencana menyimpan *masukan* (lokasi, jenis kegiatan, parameter, kondisi eksisting),
bukan hasil. Hasil dihitung ulang saat dibutuhkan, jadi ganti bahasa tetap konsisten.
"""

import io
import json
import uuid
from dataclasses import dataclass, field

from .i18n import t
from .scenarios import SCENARIOS


@dataclass
class Plan:
    name: str
    scenario_key: str
    params: dict
    area: dict  # GeoJSON geometry
    existing: object  # ExistingCondition (termasuk koreksi user)
    address: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])


def compute(scenario_key: str, params: dict, existing, lang: str = "id"):
    return SCENARIOS[scenario_key].run(existing, params, lang)


def signature(scenario_key: str, params: dict, existing) -> str:
    """Sidik unik masukan, dipakai untuk menyimpan penjelasan/chat Gemma per hasil."""
    raw = json.dumps([scenario_key, params, existing.to_dict()], sort_keys=True, default=str)
    return uuid.uuid5(uuid.NAMESPACE_OID, raw).hex[:12]


def comparison_rows(plans: list, lang: str = "id") -> list:
    rows = []
    for plan in plans:
        r = compute(plan.scenario_key, plan.params, plan.existing, lang)
        tl = {p["key"]: p for p in r.timeline}
        row = {
            t("col.name", lang): plan.name,
            t("col.kind", lang): r.scenario_label,
            t("col.location", lang): plan.address or "-",
            t("col.land", lang): round(plan.params["luas_lahan_m2"]),
            t("col.idx_c", lang): tl["konstruksi"]["indeks_risiko"],
            t("col.idx_o", lang): tl["10th"]["indeks_risiko"],
            t("col.overall", lang): t(f"level.{r.overall_level}", lang),
        }
        for c in r.components:
            row[c.name] = t(f"level.{c.level}", lang)
        row[t("col.sed", lang)] = round(tl["konstruksi"]["sedimen_ton"])
        row[t("col.co2", lang)] = round(tl["konstruksi"]["karbon_tco2"])
        row[t("col.water10", lang)] = round(tl["10th"]["air_bersih_m3"])
        row[t("col.waste10", lang)] = round(tl["10th"]["sampah_ton"])
        row[t("col.doc", lang)] = r.regulation["dokumen"]
        rows.append(row)
    return rows


def to_excel(rows: list) -> bytes:
    import pandas as pd

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df = pd.DataFrame(rows)
        df.to_excel(writer, index=False, sheet_name="AtmoSphere Sim")
        sheet = writer.sheets["AtmoSphere Sim"]
        for i, col in enumerate(df.columns, start=1):
            width = max([len(str(col))] + [len(str(v)) for v in df[col]]) + 2
            sheet.column_dimensions[sheet.cell(row=1, column=i).column_letter].width = min(width, 45)
    return buf.getvalue()
