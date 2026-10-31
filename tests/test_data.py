import json

import pytest
from shapely.geometry import shape

from atmosphere.data import DATA_PATH, ExistingDataStore
from atmosphere.geo import BATAM_CENTER, area_m2, square_around
from atmosphere.regulation import indicate_building_document


@pytest.fixture(scope="module")
def store():
    return ExistingDataStore()


class Site:
    def __init__(self, protected=False, mangrove=False):
        self.in_protected_area = protected
        self.touches_mangrove = mangrove


def test_square_has_requested_area():
    sq = square_around(104.03, 1.10, 10_000)
    assert area_m2(sq) == pytest.approx(10_000, rel=0.01)


def test_query_on_land_returns_conditions(store):
    lat, lon = BATAM_CENTER
    ex = store.query(square_around(lon, lat, 40_000))
    assert ex is not None
    assert sum(ex.land_cover_share.values()) == pytest.approx(1.0)
    assert ex.hsg in "ABCD"
    assert ex.is_dummy
    assert ex.to_dict()["data_dummy"] is True


def test_query_in_open_sea_returns_none(store):
    assert store.query(square_around(103.50, 0.50, 10_000)) is None


def test_mangrove_cell_is_flagged(store):
    feats = json.load(open(DATA_PATH, encoding="utf-8"))["features"]
    cell = next(f for f in feats if f["properties"]["tutupan_lahan"] == "mangrove")
    c = shape(cell["geometry"]).centroid
    ex = store.query(square_around(c.x, c.y, 2_000))
    assert ex.touches_mangrove


@pytest.mark.parametrize(
    "land, floor, site, expected",
    [
        (1_000, 1_500, Site(), "SPPL"),
        (10_000, 8_000, Site(), "UKL-UPL"),
        (60_000, 20_000, Site(), "AMDAL"),
        (1_000, 1_000, Site(mangrove=True), "AMDAL"),
    ],
)
def test_document_indication(land, floor, site, expected):
    out = indicate_building_document(land, floor, site)
    assert out["dokumen"] == expected
    assert out["alasan"] and out["catatan"]
    assert indicate_building_document(land, floor, site, "en")["catatan"].startswith("This is")
