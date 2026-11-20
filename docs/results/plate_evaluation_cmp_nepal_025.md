# Plate evaluation — cmp_nepal_025

Run on 2026-11-20 22:39 with `python scripts/evaluate.py`. Folder: `data/test_plates`, 132 images. Plate model: `hf://krishnamishra8848/Nepal-Vehicle-License-Plate-Detection/last.pt`. CPU only.

| Metric | Result | Target | Status |
|---|---|---|---|
| Images with a plate found (no labels) | 96/117 = **82%** | ≥ 90% | below target |
| OCR exact match (single image, known plates) | 58/116 = **50%** | ≥ 85% | below target |
| Photos without a plate where a plate was wrongly read | 0/15 | 0 | PASS |
| Plate detection time | 161 ms per image | — | — |
| OCR time | 1484 ms per image | — | — |

Known plates come from file names and checked rows of `plates.csv`. Single-image OCR is stricter than the live pipeline, which votes over several frames.

## Missed or wrong reads

- kar1.jpg: read nothing
- kar103.jpeg: read nothing
- kar107.jpeg: read ['KA20EO2292']
- kar111.jpeg: read ['KA19HH2134']
- kar114.jpeg: read ['KA19HR3611']
- kar117.jpeg: read ['KA19HY2103']
- kar119.jpeg: read nothing
- kar122.jpeg: read nothing
- kar124.jpeg: read ['KA19HG7405']
- kar127.jpeg: read nothing
- kar128.jpeg: read ['KA19HN0115']
- kar129.jpeg: read nothing
- kar130.jpeg: read nothing
- kar131.jpeg: read nothing
- kar132.jpeg: read nothing
- kar16.jpg: read ['RJ28IA5599']
- kar19.jpg: read nothing
- kar20.jpeg: read nothing
- kar21.png: read nothing
- kar22.png: read nothing
- kar23.png: read nothing
- kar24.png: read nothing
- kar25.png: read nothing
- kar26.png: read nothing
- kar36.jpeg: read ['KA21MD2880']
- kar38.jpeg: read nothing
- kar44.jpeg: read ['KA20EP8553']
- kar48.jpeg: read ['KA17HN0229']
- kar50.jpeg: read nothing
- kar51.jpeg: read nothing
- kar53.jpeg: read ['KA02HO9484']
- kar54.jpeg: read nothing
- kar56.jpeg: read ['KL26O2085']
- kar57.jpeg: read ['KA19HK0048']
- kar58.jpeg: read nothing
- kar59.jpeg: read nothing
- kar63.jpeg: read ['KA19HIC5630']
- kar65.jpeg: read nothing
- kar66.jpeg: read ['KA21EB0213']
- kar67.jpeg: read ['KA12NOR9977']
- kar68.jpeg: read nothing
- kar69.jpeg: read nothing
- kar70.jpeg: read nothing
- kar71.jpeg: read ['KA19I9026']
- kar73.jpeg: read nothing
- kar75.jpeg: read nothing
- kar76.jpeg: read nothing
- kar8.jpg: read ['TN18O1868']
- kar80.jpeg: read ['KA19H7018']
- kar85.jpeg: read nothing
- kar86.jpeg: read nothing
- kar87.jpeg: read ['KA17EG1850']
- kar89.jpeg: read nothing
- kar90.jpeg: read nothing
- kar91.jpeg: read nothing
- kar94.jpeg: read nothing
- kar95.jpeg: read ['KL14AA8810']
- kar99.jpeg: read nothing
