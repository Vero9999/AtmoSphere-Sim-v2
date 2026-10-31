"""Kontrak dasar skenario kegiatan.

Untuk menambah skenario baru: buat modul baru di folder ini yang mewarisi
`Scenario`, isi `params` dan `run()`, lalu daftarkan di `__init__.py`.
Label dan teks bantuan parameter ada di `atmosphere/i18n.py` (kunci p.<key> dan h.<key>).
"""

from dataclasses import dataclass

from ..i18n import t


@dataclass
class Param:
    key: str
    kind: str  # "int" | "float" | "bool" | "text"
    default: float | int | bool | str
    unit: str = ""  # kunci satuan di i18n, mis. "m2" -> "u.m2"
    min_value: float | None = 0

    def label(self, lang: str = "id") -> str:
        base = t(f"p.{self.key}", lang)
        return f"{base} ({t('u.' + self.unit, lang)})" if self.unit else base

    def help(self, lang: str = "id") -> str | None:
        key = f"h.{self.key}"
        text = t(key, lang)
        return None if text == key else text


class Scenario:
    key: str = ""
    available: bool = True
    params: list = []

    def label(self, lang: str = "id") -> str:
        return t(f"sc.{self.key}", lang)

    def description(self, lang: str = "id") -> str:
        return t(f"sc.{self.key}.desc", lang)

    def example_text(self, lang: str = "id") -> str:
        return t(f"sc.{self.key}.example", lang)

    def defaults(self, area_m2: float | None = None) -> dict:
        return {p.key: p.default for p in self.params}

    def run(self, existing, params: dict, lang: str = "id"):
        raise NotImplementedError


class ComingSoonScenario(Scenario):
    available = False

    def __init__(self, key: str):
        self.key = key
