# Plate evaluation — finetuned

Run on 2026-11-20 22:22 with `python scripts/evaluate.py`. Folder: `data/test_plates`, 132 images. Plate model: `settings.yaml detection.plate_model`. CPU only.

| Metric | Result | Target | Status |
|---|---|---|---|
| Images with a plate found (no labels) | 102/117 = **87%** | ≥ 90% | below target |
| OCR exact match (single image, known plates) | 72/116 = **62%** | ≥ 85% | below target |
| Photos without a plate where a plate was wrongly read | 0/15 | 0 | PASS |
| Plate detection time | 191 ms per image | — | — |
| OCR time | 3828 ms per image | — | — |

Known plates come from file names and checked rows of `plates.csv`. Single-image OCR is stricter than the live pipeline, which votes over several frames.

## Missed or wrong reads

- kar1.jpg: read nothing
- kar101.jpeg: read nothing
- kar103.jpeg: read nothing
- kar107.jpeg: read ['KA20EO2292']
- kar114.jpeg: read ['KA19R3611']
- kar117.jpeg: read ['KA19HY2189']
- kar122.jpeg: read nothing
- kar124.jpeg: read ['KA10HG7405']
- kar129.jpeg: read nothing
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
- kar29.jpeg: read nothing
- kar36.jpeg: read ['KA21MD2880']
- kar38.jpeg: read nothing
- kar39.jpeg: read nothing
- kar44.jpeg: read ['KA20P8538']
- kar51.jpeg: read nothing
- kar53.jpeg: read ['KA02HO9284']
- kar56.jpeg: read ['KL26O2085']
- kar57.jpeg: read ['KA19HK0048']
- kar58.jpeg: read nothing
- kar6.jpg: read ['PB43E9889']
- kar66.jpeg: read ['KA21SB0223']
- kar67.jpeg: read ['KA12NGR9977']
- kar69.jpeg: read nothing
- kar70.jpeg: read nothing
- kar71.jpeg: read ['KA19IG9102', 'KA11G9026']
- kar74.jpeg: read ['KL14B0318']
- kar75.jpeg: read ['KL14NOP5537']
- kar76.jpeg: read nothing
- kar8.jpg: read ['TN18O1868']
- kar80.jpeg: read ['KA19H4001']
- kar87.jpeg: read ['KA47EG1850']
- kar90.jpeg: read ['KA19HG3271', 'KA19H6327']
- kar95.jpeg: read ['KL14A7810']
- kar97.jpeg: read nothing
