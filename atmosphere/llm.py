"""Klien Gemma 4.

Peran Gemma di aplikasi ini:
1. Mengubah deskripsi kegiatan berbahasa awam menjadi parameter terstruktur.
2. Menjelaskan hasil prediksi dalam bahasa sederhana (streaming).
3. Membandingkan foto lokasi dari user dengan data kondisi eksisting (multimodal).
4. Menjawab pertanyaan user tentang hasil (streaming).

Gemma TIDAK menghitung angka dampak; angka berasal dari model di `models.py`.
Gemma menjawab langsung dalam bahasa yang dipilih user (id/en), bukan menerjemahkan.

Backend diatur lewat variabel lingkungan (lihat `.env.example`):
- LLM_BACKEND=google  -> Gemma lewat Google AI Studio (Gemini API)
- LLM_BACKEND=ollama  -> Gemma lokal lewat Ollama
- LLM_BACKEND=mock    -> mode demo tanpa LLM (default)
"""

import base64
import json
import os
import re
import time
from typing import Iterator

import requests

TIMEOUT_S = 60
# Gemma 4 di Gemini API "berpikir" dulu sebelum menjawab. Level "minimal" membuat teks
# pertama muncul ±2 detik (bukan ±18 detik) dengan kualitas yang cukup untuk aplikasi ini.
THINKING_LEVEL = os.getenv("GEMMA_THINKING", "minimal")

SYSTEM_PROMPT = {
    "id": (
        "Kamu adalah asisten AtmoSphere Sim, alat prediksi dampak lingkungan untuk Kota Batam. "
        "Penggunamu masyarakat umum, jadi pakai bahasa Indonesia yang sederhana dan hindari istilah teknis. "
        "Jangan pernah mengarang angka: gunakan hanya angka yang diberikan di konteks. "
        "Jika ditanya hal di luar data, katakan terus terang bahwa datanya tidak tersedia. "
        "Selalu jawab dalam bahasa Indonesia."
    ),
    "en": (
        "You are the assistant of AtmoSphere Sim, an environmental impact prediction tool for Batam, Indonesia. "
        "Your users are the general public, so use simple English and avoid jargon. "
        "Never invent numbers: only use numbers given in the context. "
        "If asked about something outside the data, say plainly that the data is not available. "
        "Keep Indonesian terms like AMDAL, UKL-UPL, SPPL and ruko, with a short explanation. "
        "Always answer in English."
    ),
}

DEMO = {
    "id": {
        "photo": "Mode demo: analisis foto membutuhkan Gemma 4 aktif (atur LLM_BACKEND di file .env).",
        "answer": "Mode demo: fitur tanya-jawab membutuhkan Gemma 4 aktif.",
        "overall": "Tingkat dampak keseluruhan",
        "high": "Dampak yang perlu perhatian utama",
        "mid": "Dampak sedang",
        "tips": "Langkah yang disarankan",
        "doc": "Indikasi dokumen lingkungan",
        "note": "_(Penjelasan otomatis mode demo. Aktifkan Gemma 4 untuk penjelasan yang lebih kaya.)_",
        "failed": "Gemma gagal dipanggil ({err}). Memakai mode demo.",
    },
    "en": {
        "photo": "Demo mode: photo analysis needs Gemma 4 enabled (set LLM_BACKEND in .env).",
        "answer": "Demo mode: Q&A needs Gemma 4 enabled.",
        "overall": "Overall impact level",
        "high": "Impacts needing the most attention",
        "mid": "Medium impacts",
        "tips": "Suggested steps",
        "doc": "Indicated environmental document",
        "note": "_(Automatic demo-mode explanation. Enable Gemma 4 for a richer explanation.)_",
        "failed": "Gemma call failed ({err}). Using demo mode.",
    },
}
LEVEL_WORD = {"en": {"rendah": "low", "sedang": "medium", "tinggi": "high"}}


# --- utilitas -------------------------------------------------------------------
def _parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}


def _to_number(raw: str) -> float:
    """'4.000' -> 4000, '4,000' -> 4000, '2,5' -> 2.5"""
    raw = re.sub(r"(?<=\d)[.,](?=\d{3}(\D|$))", "", raw)
    return float(raw.replace(",", "."))


def compact_context(result_dict: dict) -> dict:
    """Versi ringkas hasil untuk prompt: lebih sedikit token = Gemma lebih cepat."""
    r = result_dict
    return {
        "kegiatan": r.get("scenario_label"),
        "tingkat_keseluruhan": r.get("tingkat_dampak_keseluruhan"),
        "parameter": r.get("params"),
        "kondisi_saat_ini": {k: v for k, v in (r.get("existing") or {}).items() if k != "koreksi_user"},
        "dampak": [
            {"nama": c["name"], "tingkat": c["level"], "ringkasan": c["summary"], "mitigasi": c["mitigation"][:2]}
            for c in r.get("components", [])
        ],
        "per_periode": [
            {k: (round(v) if isinstance(v, float) else v) for k, v in p.items() if k != "key"}
            for p in r.get("timeline", [])
        ],
        "dokumen_lingkungan": (r.get("regulation") or {}).get("dokumen"),
        "asumsi": r.get("assumptions"),
    }


def coerce(value, kind: str):
    """Ubah nilai dari LLM ke tipe parameter. None/kosong/tidak valid -> None (diabaikan)."""
    if value is None or value == "":
        return None
    try:
        if kind == "bool":
            if isinstance(value, str):
                return value.strip().lower() in ("true", "ya", "yes", "1")
            return bool(value)
        if kind == "text":
            return str(value).strip() or None
        number = _to_number(value) if isinstance(value, str) else float(value)
        if number < 0:
            return None
        return int(round(number)) if kind == "int" else number
    except (TypeError, ValueError):
        return None


SCENARIO_WORDS = [
    ("hotel", r"hotel|penginapan|resort|guest ?house|kamar|rooms?\b"),
    ("mal", r"\bmal\b|\bmall\b|pusat perbelanjaan|pertokoan|shopping"),
    ("kantor", r"kantor|perkantoran|office|karyawan|employees?"),
    ("ruko", r"\bruko\b|rumah toko|shop ?houses?"),
    ("perumahan", r"perumahan|\brumah\b|houses?\b|housing|homes?\b|kavling"),
]


def guess_scenario(text: str) -> str | None:
    t = text.lower()
    for key, pattern in SCENARIO_WORDS:
        if re.search(pattern, t):
            return key
    return "lainnya" if t.strip() else None


def rule_based_extract(text: str) -> dict:
    """Ekstraksi sederhana berbasis pola (ID + EN), dipakai di mode demo atau saat LLM gagal."""
    t = text.lower()
    num = r"(\d[\d.,]*)"
    m2 = r"\s*(?:m2|m²|meter persegi|square met(?:er|re)s?|sqm)"
    out = {}

    def find(pattern):
        m = re.search(pattern, t)
        return _to_number(m.group(1)) if m else None

    lahan = find(num + r"\s*(?:ha|hektar|hectares?)\b")
    if lahan is not None:
        out["luas_lahan_m2"] = lahan * 10_000
    else:
        lahan = find(num + m2 + r"\s*(?:of )?(?:land|lahan)")
        if lahan is None:
            lahan = find(r"(?:lahan|land)[^\d]{0,20}" + num + m2)
        if lahan is None:
            lahan = find(num + m2)
        if lahan is not None:
            out["luas_lahan_m2"] = lahan
    rules = [
        ("luas_tapak_bangunan_m2", r"(?:tapak|footprint)[^\d]{0,25}" + num, float),
        ("luas_perkerasan_m2", r"(?:jalan|parkir|roads?|parking)[^\d]{0,25}" + num, float),
        ("jumlah_lantai", num + r"\s*(?:lantai|floors?|stor(?:e)?y|storeys|stories)", int),
        ("jumlah_lantai", num + r"-(?:stor(?:e)?y|floor)", int),
        ("jumlah_unit", num + r"\s*(?:unit|rumah|ruko|kavling|houses?|homes?|shop ?houses?)", int),
        ("jumlah_karyawan", num + r"\s*(?:karyawan|pegawai|employees?|staff|workers?)", int),
        ("jumlah_kamar", num + r"\s*(?:kamar|rooms?)", int),
        ("pengunjung_per_hari", num + r"\s*(?:pengunjung|visitors?)", int),
        ("jumlah_orang", num + r"\s*(?:siswa|murid|jemaah|orang|students?|people|persons?)", int),
        ("durasi_konstruksi_bulan", num + r"\s*(?:bulan|months?)", int),
    ]
    for key, pattern, cast in rules:
        if key in out:
            continue
        v = find(pattern)
        if v is not None:
            out[key] = cast(v)
    if re.search(r"cut\s*(?:and|&|n)?\s*fill|potong bukit|pangkas bukit|urug|perataan bukit|hilly|berbukit", t):
        out["cut_and_fill"] = True
    if re.search(r"silt fence|terasering|terrac|pengendali erosi|erosion control", t):
        out["pengendali_erosi"] = True
    return out


# --- klien ----------------------------------------------------------------------
class GemmaClient:
    def __init__(self):
        self.backend = os.getenv("LLM_BACKEND", "mock").strip().lower()
        default_model = {"ollama": "gemma4:e4b", "google": "gemma-4-26b-a4b-it"}.get(self.backend, "")
        self.model = os.getenv("GEMMA_MODEL") or default_model
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.last_error: str | None = None
        self._google = None
        if self.backend == "google":
            try:
                from google import genai
                from google.genai import types

                self._google = genai.Client(
                    api_key=os.getenv("GOOGLE_API_KEY"),
                    http_options=types.HttpOptions(timeout=TIMEOUT_S * 1000),
                )
            except Exception as exc:  # paket belum terpasang / API key kosong
                self.last_error = f"Google GenAI: {exc}"
                self.backend = "mock"

    @property
    def is_mock(self) -> bool:
        return self.backend not in ("ollama", "google")

    @property
    def label(self) -> str:
        if self.is_mock:
            return "Demo"
        return f"{self.model} · {self.backend}"

    # --- pemanggilan model ----------------------------------------------------
    def _google_contents(self, prompt, lang, images):
        from google.genai import types

        # Gemma di Gemini API tidak mendukung system instruction, jadi digabung ke prompt.
        contents = [f"{SYSTEM_PROMPT[lang]}\n\n{prompt}"]
        for data, mime in images or []:
            contents.append(types.Part.from_bytes(data=data, mime_type=mime))
        return contents

    def _ollama_body(self, prompt, lang, images, stream, json_mode=False):
        msg = {"role": "user", "content": prompt}
        if images:
            msg["images"] = [base64.b64encode(data).decode() for data, _ in images]
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT[lang]}, msg],
            "stream": stream,
        }
        if json_mode:
            body["format"] = "json"
        return body

    def _google_config(self):
        from google.genai import types

        if not THINKING_LEVEL:
            return None
        return types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=THINKING_LEVEL))

    def _chat(self, prompt: str, lang: str = "id", images: list | None = None, json_mode: bool = False) -> str:
        if self.backend == "google":
            resp = self._google.models.generate_content(
                model=self.model, contents=self._google_contents(prompt, lang, images), config=self._google_config()
            )
            return resp.text or ""
        if self.backend == "ollama":
            resp = requests.post(f"{self.ollama_url}/api/chat",
                                 json=self._ollama_body(prompt, lang, images, False, json_mode), timeout=TIMEOUT_S * 3)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        raise RuntimeError("LLM backend not active")

    def _stream(self, prompt: str, lang: str = "id") -> Iterator[str]:
        if self.backend == "google":
            for chunk in self._google.models.generate_content_stream(
                model=self.model, contents=self._google_contents(prompt, lang, None), config=self._google_config()
            ):
                if chunk.text:
                    yield chunk.text
            return
        if self.backend == "ollama":
            with requests.post(f"{self.ollama_url}/api/chat", json=self._ollama_body(prompt, lang, None, True),
                               stream=True, timeout=TIMEOUT_S * 3) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        piece = json.loads(line).get("message", {}).get("content", "")
                        if piece:
                            yield piece
            return
        raise RuntimeError("LLM backend not active")

    def _try(self, fn, fallback, lang="id"):
        if self.is_mock:
            return fallback()
        self.last_error = None
        error = None
        for attempt in range(2):  # server kadang membalas 500/503 sesaat; coba sekali lagi
            try:
                return fn()
            except Exception as exc:
                error = exc
                if attempt == 0:
                    time.sleep(1)
        self.last_error = DEMO[lang]["failed"].format(err=str(error)[:160])
        return fallback()

    def _try_stream(self, prompt, fallback_text, lang="id") -> Iterator[str]:
        """Streaming dengan cadangan: kalau gagal sebelum ada teks, pakai teks demo."""
        if self.is_mock:
            yield fallback_text
            return
        self.last_error = None
        got_any = False
        try:
            for piece in self._stream(prompt, lang):
                got_any = True
                yield piece
        except Exception as exc:
            self.last_error = DEMO[lang]["failed"].format(err=str(exc)[:160])
            if not got_any:
                yield fallback_text

    # --- fitur ----------------------------------------------------------------
    def extract_params(self, text: str, scenario, lang: str = "id") -> dict:
        """Teks bebas -> {param: nilai, "pertanyaan": [...], "jenis_kegiatan": key}."""
        from .scenarios import SCENARIOS

        kinds = [k for k, s in SCENARIOS.items() if s.available]
        # Semua kunci dari semua jenis kegiatan, supaya kalau Gemma mendeteksi jenis lain
        # (mis. user memilih Rumah tapi menulis "hotel 120 kamar"), datanya tidak hilang.
        all_params = {p.key: p for p in scenario.params}
        for k in kinds:
            for p in SCENARIOS[k].params:
                all_params.setdefault(p.key, p)
        keys = {k: f"{p.label('en')} ({p.kind})" for k, p in all_params.items()}

        def call():
            prompt = (
                "Convert the activity description below into JSON using only the available keys.\n"
                f"Available keys: {json.dumps(keys, ensure_ascii=False)}\n"
                "Fill only keys that are stated or clearly implied. Use the requested units "
                "(convert hectares to m²). Booleans as true/false. Numbers without thousand separators.\n"
                f"Also add \"jenis_kegiatan\": the best match from {kinds} "
                "(use \"lainnya\" for schools, places of worship, warehouses, etc).\n"
                f"Also add \"pertanyaan\": a list of at most 3 short questions, in "
                f"{'Indonesian' if lang == 'id' else 'English'}, for important missing info.\n\n"
                f"Description: {text}\n\nReply with JSON ONLY."
            )
            data = _parse_json(self._chat(prompt, lang, json_mode=True))
            return data or self._rule_extract(text)

        result = self._try(call, lambda: self._rule_extract(text), lang)
        kinds_by_key = {k: p.kind for k, p in all_params.items()}
        out = {}
        for k, v in result.items():
            if k in kinds_by_key and (clean := coerce(v, kinds_by_key[k])) is not None:
                out[k] = clean
        if result.get("pertanyaan"):
            out["pertanyaan"] = [str(q) for q in result["pertanyaan"]][:3]
        if result.get("jenis_kegiatan") in kinds:
            out["jenis_kegiatan"] = result["jenis_kegiatan"]
        return out

    @staticmethod
    def _rule_extract(text):
        out = rule_based_extract(text)
        kind = guess_scenario(text)
        if kind:
            out["jenis_kegiatan"] = kind
        return out

    def explain_stream(self, result_dict: dict, lang: str = "id") -> Iterator[str]:
        ctx = json.dumps(compact_context(result_dict), ensure_ascii=False, default=str)
        prompt = {
            "id": "Berikut hasil prediksi dampak lingkungan (JSON). Jelaskan ke warga awam dalam 3-4 paragraf "
                  "pendek: dampak terbesar dan kenapa, bagaimana dampaknya bertambah dari saat konstruksi sampai "
                  "10 tahun, dan 3 langkah terpenting. Sebutkan ini prediksi awal dan sebutkan indikasi dokumen "
                  "lingkungannya.",
            "en": "Here is an environmental impact prediction (JSON). Explain it to a member of the public in 3-4 "
                  "short paragraphs: the biggest impacts and why, how impacts build up from construction to 10 "
                  "years, and the 3 most important steps. Say this is an early prediction and mention the "
                  "indicated environmental document.",
        }[lang]
        return self._try_stream(f"{prompt}\n\n{ctx}", self.template_explain(result_dict, lang), lang)

    def answer_stream(self, question: str, result_dict: dict, history: list | None = None,
                      lang: str = "id") -> Iterator[str]:
        ctx = json.dumps(compact_context(result_dict), ensure_ascii=False, default=str)
        past = "\n".join(f"{m['role']}: {m['content']}" for m in (history or [])[-6:])
        prompt = (
            f"Context (prediction result JSON):\n{ctx}\n\n"
            + (f"Previous conversation:\n{past}\n\n" if past else "")
            + f"User question: {question}\nAnswer briefly, based on the context."
        )
        return self._try_stream(prompt, DEMO[lang]["answer"], lang)

    def check_photo(self, image: bytes, mime: str, existing_dict: dict, lang: str = "id") -> str:
        def call():
            prompt = {
                "id": "Ini foto lokasi dari pengguna. Menurut data kami, kondisi area ini adalah:\n{d}\n\n"
                      "Jelaskan singkat apa yang terlihat di foto (tutupan lahan, vegetasi, bangunan, air, "
                      "kemiringan). Lalu nilai: SESUAI, SEBAGIAN SESUAI, atau TIDAK SESUAI dengan data, dan "
                      "sarankan koreksi tutupan lahan jika perlu.",
                "en": "This is a site photo from the user. According to our data, the area's current condition "
                      "is:\n{d}\n\nBriefly describe what the photo shows (land cover, vegetation, buildings, water, "
                      "slope). Then rate it: MATCHES, PARTLY MATCHES, or DOES NOT MATCH the data, and suggest a "
                      "land-cover correction if needed.",
            }[lang].format(d=json.dumps(existing_dict, ensure_ascii=False))
            return self._chat(prompt, lang, images=[(image, mime)])

        return self._try(call, lambda: DEMO[lang]["photo"], lang)

    @staticmethod
    def template_explain(r: dict, lang: str = "id") -> str:
        d = DEMO[lang]
        word = LEVEL_WORD.get(lang, {})
        comps = r.get("components", [])
        high = [c["name"] for c in comps if c["level"] == "tinggi"]
        mid = [c["name"] for c in comps if c["level"] == "sedang"]
        overall = r.get("tingkat_dampak_keseluruhan", "-")
        lines = [f"{d['overall']}: **{word.get(overall, overall)}**."]
        if high:
            lines.append(f"{d['high']}: " + ", ".join(high) + ".")
        if mid:
            lines.append(f"{d['mid']}: " + ", ".join(mid) + ".")
        tips = [m for c in comps if c["level"] != "rendah" for m in c.get("mitigation", [])[:1]]
        if tips:
            lines.append(f"{d['tips']}: " + " ".join(tips[:3]))
        reg = r.get("regulation", {})
        if reg:
            lines.append(f"{d['doc']}: **{reg.get('dokumen')}**. {reg.get('catatan', '')}")
        lines.append(d["note"])
        return "\n\n".join(lines)
