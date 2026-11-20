# Plate evaluation

Run on 2026-11-18 21:52 with `python scripts/evaluate.py`. Folder: `data/test_plates`, 132 images. Plate model: `settings.yaml detection.plate_model`. CPU only.

| Metric | Result | Target | Status |
|---|---|---|---|
| Images with a plate found (no labels) | 106/132 = **80%** | ≥ 90% | below target |
| OCR exact match (single image, known plates) | 0/9 = **0%** | ≥ 85% | below target |
| Photos without a plate where a plate was wrongly read | 0/0 | 0 | PASS |
| Plate detection time | 348 ms per image | — | — |
| OCR time | 5983 ms per image | — | — |

Known plates come from file names and checked rows of `plates.csv`; 90 unchecked rows were skipped. Single-image OCR is stricter than the live pipeline, which votes over several frames.

## Missed or wrong reads

- HR98AA7777.jpg: read nothing
- KA19AB1234.jpg: read nothing
- KA19EG2310.jpeg: read nothing
- KA19TR0001.png: read nothing
- KA19TR0002.png: read nothing
- KA20EF2468.png: read nothing
- KA21GH1357.png: read nothing
- KA22JK9753.png: read nothing
- KA24PQ1122.png: read nothing
