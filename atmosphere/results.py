"""Struktur data hasil prediksi."""

from dataclasses import asdict, dataclass, field

LEVEL_ORDER = {"rendah": 0, "sedang": 1, "tinggi": 2}


@dataclass
class ComponentImpact:
    key: str
    name: str
    level: str  # rendah / sedang / tinggi
    summary: str
    before: float | None = None
    after: float | None = None
    unit: str = ""
    mitigation: list = field(default_factory=list)


@dataclass
class AssessmentResult:
    scenario_key: str
    scenario_label: str
    params: dict
    existing: dict
    components: list
    regulation: dict
    assumptions: list = field(default_factory=list)

    @property
    def overall_level(self) -> str:
        if not self.components:
            return "rendah"
        return max((c.level for c in self.components), key=LEVEL_ORDER.get)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tingkat_dampak_keseluruhan"] = self.overall_level
        return d
