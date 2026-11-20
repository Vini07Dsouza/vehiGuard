# Plate evaluation — datacluster

Run on 2026-11-20 21:43 with `python scripts/evaluate.py`. Folder: `data/datasets/datacluster_eval/images`, 47 images. Plate model: `settings.yaml detection.plate_model`. CPU only.

| Metric | Result | Target | Status |
|---|---|---|---|
| Detection recall (IoU ≥ 0.5) | 24/52 = **46%** | ≥ 90% | below target |
| Detection precision | 27/49 = 55% | — | — |
| OCR exact match (single image, known plates) | 0/0 = **0%** | ≥ 85% | below target |
| Photos without a plate where a plate was wrongly read | 0/0 | 0 | PASS |
| Plate detection time | 318 ms per image | — | — |
| OCR time | 0 ms per image | — | — |

Known plates come from file names and checked rows of `plates.csv`. Single-image OCR is stricter than the live pipeline, which votes over several frames.

## Missed or wrong reads


