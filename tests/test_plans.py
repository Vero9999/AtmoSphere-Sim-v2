import io

from atmosphere.plans import Plan, comparison_rows, compute, signature, to_excel
from atmosphere.scenarios import SCENARIOS
from tests.test_scenarios import make_existing


def make_plan(name, key, **extra):
    sc = SCENARIOS[key]
    return Plan(name, key, sc.defaults(4000) | extra, {"type": "Point", "coordinates": [104, 1]}, make_existing())


def test_compare_two_plans_in_both_languages():
    plans = [make_plan("A", "ruko", jumlah_unit=20), make_plan("B", "hotel", jumlah_kamar=120)]
    rows = comparison_rows(plans, "id")
    assert [r["Rencana"] for r in rows] == ["A", "B"]
    assert rows[0]["Dokumen"] in {"AMDAL", "UKL-UPL", "SPPL"}
    rows_en = comparison_rows(plans, "en")
    assert rows_en[1]["Plan"] == "B" and "Clean water 10 yrs (m³)" in rows_en[1]


def test_excel_export_opens():
    import openpyxl

    data = to_excel(comparison_rows([make_plan("A", "kantor")], "en"))
    wb = openpyxl.load_workbook(io.BytesIO(data))
    assert wb.active["A2"].value == "A"


def test_signature_changes_with_params():
    ex = make_existing()
    a = signature("ruko", {"x": 1}, ex)
    assert a == signature("ruko", {"x": 1}, ex)
    assert a != signature("ruko", {"x": 2}, ex)
    assert compute("ruko", SCENARIOS["ruko"].defaults(1000), ex).components
