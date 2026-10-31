# 🌏 AtmoSphere Sim

[![tests](https://github.com/Vero9999/AtmoSphere-Sim-v2/actions/workflows/tests.yml/badge.svg)](https://github.com/Vero9999/AtmoSphere-Sim-v2/actions/workflows/tests.yml)
![Hacktoberfest](https://img.shields.io/badge/Hacktoberfest-2026-blueviolet)
![Gemma 4](https://img.shields.io/badge/AI-Gemma%204-0E7490)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Environmental impact prediction for building plans in Batam, Indonesia — explained in plain language by Gemma 4.**

Pick a site on the map, describe what you want to build in everyday words (or upload a site plan), and
AtmoSphere Sim predicts the impact on flooding, erosion, water, waste and carbon — during construction and
1, 5 and 10 years later — with practical steps to reduce it.

> ⚠️ **For preliminary screening only.** Results are not an official environmental impact analysis and do not
> replace an AMDAL, UKL-UPL, SPPL or any other environmental document. Environmental data is still **dummy**.
> Results must be reviewed by a qualified environmental expert.

**Live demo:** _coming soon_ · Built at Hacktoberfest Hack Day Kota Batam × Batam Innovation Center 2026

---

## Why

Batam is growing fast. Reclamation, land clearing and new buildings have caused mangrove loss, flooding,
sediment in reservoirs, and pressure on a water supply that depends on rain-fed reservoirs. Most residents
and small developers have no easy way to see the environmental effect of a plan *before* they build.
AtmoSphere Sim gives them a first look in minutes, in Indonesian or English.

## Features

| | |
|---|---|
| 🗺️ **Map** | Draw the site or click a point (OpenStreetMap / Esri satellite). Shows the approximate address and locks the location. |
| 🌿 **Current conditions** | Land cover, slope, rainfall, PM2.5, mangrove and protected-area warnings. Users can correct the data. |
| 🏗️ **6 activity types** | House/housing, shophouse (ruko), office, hotel, mall, and *Other* (school, warehouse, …) with its own name and water use. |
| ✨ **Plain-language input** | Describe the plan in a sentence, or upload a **site plan image** — Gemma 4 fills in the form and detects the activity type. |
| 📈 **Results over time** | Risk index and running totals for construction, 1, 5 and 10 years; impact cards with mitigation steps. |
| 📄 **Permit indication** | Indicates AMDAL / UKL-UPL / SPPL (placeholder thresholds, clearly labelled). |
| 🤖 **Gemma explains** | Streaming plain-language explanation and a Q&A chat about the result. |
| 📊 **Compare plans** | Save several plans, compare them side by side, download the comparison as Excel. |
| 🌐 **Bilingual** | Bahasa Indonesia / English, including Gemma's answers. |

## How Gemma 4 is used

Gemma 4 (`gemma-4-26b-a4b-it` via the Gemini API, or locally via Ollama) does the language and vision work.
**It never produces the impact numbers** — those come from transparent formulas, so results are reproducible.

| Task | Input | Output |
|---|---|---|
| Plan extraction | Free text (ID/EN) and/or a **site plan image** | Structured parameters + activity type + follow-up questions |
| Site photo check | **Site photo** + current-condition data | Match / partial / no match, with suggested correction |
| Explanation | Result JSON | Plain-language summary in the user's language (streamed) |
| Q&A | Question + result JSON + chat history | Short grounded answer (streamed) |

Speed note: Gemma 4 "thinks" before answering by default. Setting `thinking_level="minimal"` cut the time to
first word from ~18 s to ~2 s in our tests, which made the app usable.

## How the numbers are calculated

| Impact | Method |
|---|---|
| Stormwater runoff | SCS Curve Number (USDA TR-55), 100 mm design storm |
| Construction erosion | USLE (A = R·K·LS·C·P), R from Lenvain; Indonesian erosion hazard classes |
| Clean water / wastewater / waste | Per-person rates per activity type (e.g. 150 L/day for homes, 250 L/guest for hotels) |
| Carbon | Loss of biomass carbon stock × 44/12 |
| Sensitive areas | Overlap with mangrove or protected areas → high + AMDAL indication |
| Risk index | Average of continuous 0–100 scores of the impacts active in each period |

Every coefficient is in [`atmosphere/config.py`](atmosphere/config.py) with its source or an `ASUMSI`
(assumption) label, and every result lists the assumptions used.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # set LLM_BACKEND=google and GOOGLE_API_KEY (free key: aistudio.google.com/apikey)
python scripts/check_gemma.py   # optional: test all four Gemma features
streamlit run app.py
```

Without an API key the app runs in **demo mode** (pattern-based extraction and template explanations).

### Deploy on Streamlit Community Cloud

1. New app → this repo, branch `main`, file `app.py`, Python 3.12.
2. Advanced settings → Secrets: copy [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) and fill in your key.

## Tests

```bash
pytest
```

44 tests cover the formulas, data lookup, permit rules, all activity types, both languages, Gemma output
cleaning, plan comparison/Excel export, and a full click-through of the app in demo mode.

## Project structure

```
app.py                       Streamlit app (map, form, results, Gemma, saved plans)
atmosphere/
  config.py                  coefficients and assumptions
  models.py                  impact formulas and 0–100 scores
  scenarios/buildings.py     6 activity types sharing one building model + timeline
  llm.py                     Gemma 4 client (google | ollama | mock), streaming, images
  data.py, geo.py            current conditions, area, address lookup, map layer
  regulation.py              AMDAL / UKL-UPL / SPPL indication
  plans.py                   saved plans, comparison, Excel export
  i18n.py, i18n_ui.py        Indonesian / English text
  ui.py                      HTML/CSS components
data/                        dummy Batam environmental grid (GeoJSON)
scripts/                     dummy data generator, Gemma check
tests/                       pytest suite
```

## Roadmap

- Replace dummy data with ESA WorldCover land cover and DEMNAS elevation (e.g. via Google Earth Engine)
- Industry scenario (stack emissions, noise) and coastal reclamation / mangrove scenario
- Design storm from BMKG Hang Nadim rainfall data
- Verify permit thresholds against PermenLHK 4/2021 with DLH Kota Batam
- PDF report and permanent saved plans

## Ringkasan (Bahasa Indonesia)

AtmoSphere Sim memprediksi dampak lingkungan dari rencana pembangunan di Kota Batam: limpasan/banjir, erosi,
air bersih, air limbah, sampah, dan karbon, saat konstruksi sampai 10 tahun. User cukup memilih lokasi di peta
dan menceritakan rencananya (atau mengunggah siteplan); Gemma 4 mengisi formulir, menjelaskan hasil, dan menjawab
pertanyaan. **Hanya untuk kajian awal**, bukan pengganti AMDAL, UKL-UPL, SPPL, atau dokumen lingkungan lainnya.

## License

[MIT](LICENSE)
