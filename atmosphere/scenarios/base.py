"""Kontrak dasar skenario kegiatan.

Untuk menambah skenario baru: buat modul baru di folder ini yang mewarisi
`Scenario`, isi `params` dan `run()`, lalu daftarkan di `__init__.py`.
"""

from dataclasses import dataclass


@dataclass
class Param:
    key: str
    label: str
    kind: str  # "int" | "float" | "bool"
    default: float | int | bool
    help: str = ""
    unit: str = ""
    min_value: float | None = 0


class Scenario:
    key: str = ""
    label: str = ""
    description: str = ""
    example_text: str = ""
    available: bool = True
    params: list = []

    def defaults(self, area_m2: float | None = None) -> dict:
        return {p.key: p.default for p in self.params}

    def run(self, existing, params: dict):
        raise NotImplementedError


class ComingSoonScenario(Scenario):
    available = False

    def __init__(self, key: str, label: str, description: str):
        self.key, self.label, self.description = key, label, description
