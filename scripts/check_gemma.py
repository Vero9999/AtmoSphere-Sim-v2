"""Uji cepat keempat fitur Gemma 4 dengan backend di file .env.

Jalankan: python scripts/check_gemma.py [path_foto.jpg]
"""

import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

from atmosphere.data import ExistingDataStore
from atmosphere.geo import BATAM_CENTER, square_around
from atmosphere.llm import GemmaClient
from atmosphere.scenarios import SCENARIOS

load_dotenv()
llm = GemmaClient()
print(f"Backend: {llm.label}")
if llm.is_mock:
    print(f"Masih mode demo. {llm.last_error or 'Atur LLM_BACKEND di .env.'}")
    sys.exit(1)

lat, lon = BATAM_CENTER
existing = ExistingDataStore().query(square_around(lon, lat, 4000))
failed = []


def timed(name, fn):
    t = time.time()
    out = fn()
    ok = llm.last_error is None
    print(f"\n[{'OK' if ok else 'GAGAL'}] {name} ({time.time() - t:.1f}s)\n{str(out)[:400]}")
    if not ok:
        failed.append(f"{name}: {llm.last_error}")
    return out


def streamed(name, gen):
    t = time.time()
    first, text = None, ""
    for piece in gen:
        first = first or time.time() - t
        text += piece
    ok = llm.last_error is None
    print(f"\n[{'OK' if ok else 'GAGAL'}] {name} (teks pertama {first:.1f}s, selesai {time.time() - t:.1f}s)\n{text[:400]}")
    if not ok:
        failed.append(f"{name}: {llm.last_error}")


sc = SCENARIOS["lainnya"]
ex = timed("1. Ekstraksi parameter (ID)", lambda: llm.extract_params(
    "Saya mau bangun sekolah 3 lantai untuk 600 siswa di lahan 8.000 m², tapak 3.000 m², lapangan dan parkir "
    "2.000 m². Konstruksi 14 bulan.", sc, "id"))
timed("1b. Ekstraksi parameter (EN)", lambda: llm.extract_params(
    "An 8-storey hotel with 120 rooms on 5,000 m2 of land, footprint 2,000 m2, parking 1,500 m2.",
    SCENARIOS["hotel"], "en"))

params = sc.defaults(8000) | {k: v for k, v in ex.items() if k in sc.defaults()}
result = sc.run(existing, params, "en").to_dict()
streamed("2. Penjelasan hasil (EN, streaming)", llm.explain_stream(result, "en"))
streamed("3. Tanya-jawab (EN, streaming)", llm.answer_stream("How big should my infiltration wells be?", result, lang="en"))

if len(sys.argv) > 1:
    path = Path(sys.argv[1])
    img, mime = path.read_bytes(), "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
else:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (480, 320), (60, 120, 60))  # gambar uji: vegetasi + jalan + atap
    d = ImageDraw.Draw(im)
    d.rectangle([0, 220, 480, 260], fill=(90, 90, 90))
    d.rectangle([300, 60, 440, 200], fill=(170, 60, 50))
    buf = io.BytesIO()
    im.save(buf, "JPEG")
    img, mime = buf.getvalue(), "image/jpeg"
timed("4. Cek foto (ID, multimodal)", lambda: llm.check_photo(img, mime, existing.to_dict(), "id"))

print("\n" + ("Semua fitur Gemma berjalan." if not failed else "Ada yang gagal:\n- " + "\n- ".join(failed)))
sys.exit(1 if failed else 0)
