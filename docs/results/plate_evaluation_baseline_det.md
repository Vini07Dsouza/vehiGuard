# Plate evaluation — baseline_det

Run on 2026-11-20 22:11 with `python scripts/evaluate.py`. Folder: `data/test_plates`, 132 images. Plate model: `settings.yaml detection.plate_model`. CPU only.

| Metric | Result | Target | Status |
|---|---|---|---|
| Images with a plate found (no labels) | 96/117 = **82%** | ≥ 90% | below target |
| OCR exact match (single image, known plates) | 0/0 = **0%** | ≥ 85% | below target |
| Photos without a plate where a plate was wrongly read | 0/15 | 0 | PASS |
| Plate detection time | 86 ms per image | — | — |
| OCR time | 0 ms per image | — | — |

Known plates come from file names and checked rows of `plates.csv`. Single-image OCR is stricter than the live pipeline, which votes over several frames.

## Missed or wrong reads


