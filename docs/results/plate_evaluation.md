# Plate evaluation

Run on 2026-11-20 21:23 with `python scripts/evaluate.py`. Folder: `data/test_plates`, 132 images. Plate model: `settings.yaml detection.plate_model`. CPU only.

| Metric | Result | Target | Status |
|---|---|---|---|
| Images with a plate found (no labels) | 96/117 = **82%** | ≥ 90% | below target |
| OCR exact match (single image, known plates) | 57/116 = **49%** | ≥ 85% | below target |
| Photos without a plate where a plate was wrongly read | 0/15 | 0 | PASS |
| Plate detection time | 326 ms per image | — | — |
| OCR time | 42473 ms per image | — | — |

Known plates come from file names and checked rows of `plates.csv`. Single-image OCR is stricter than the live pipeline, which votes over several frames.

## Missed or wrong reads

- kar1.jpg: read nothing
- kar101.jpeg: read ['KA19HUX3151']
- kar102.jpeg: read ['KA19HC0478']
- kar103.jpeg: read nothing
- kar107.jpeg: read ['KA20EO2292']
- kar109.jpeg: read ['KA20HO5248']
- kar111.jpeg: read ['KA19HH2134']
- kar114.jpeg: read ['KA19HR3611']
- kar117.jpeg: read ['KA19HY2103']
- kar120.jpeg: read ['KA19HLH6784']
- kar122.jpeg: read nothing
- kar123.jpeg: read ['KL14OB1230']
- kar124.jpeg: read ['KA19HG7405']
- kar128.jpeg: read ['KA19HLV1570']
- kar129.jpeg: read nothing
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
- kar29.jpeg: read ['KA19HL1269']
- kar36.jpeg: read ['KA21MD2880']
- kar38.jpeg: read nothing
- kar44.jpeg: read ['KA20EP8553']
- kar46.jpeg: read ['KA19HCK0767']
- kar48.jpeg: read ['KA17H7229']
- kar50.jpeg: read ['KL60L9185']
- kar51.jpeg: read nothing
- kar54.jpeg: read nothing
- kar56.jpeg: read ['KL26O2085']
- kar57.jpeg: read ['KA19HK0048']
- kar58.jpeg: read nothing
- kar59.jpeg: read nothing
- kar63.jpeg: read ['KA19HIC5630']
- kar64.jpeg: read ['KA19HCP5739']
- kar65.jpeg: read ['KL12P5537']
- kar66.jpeg: read ['KA21EB0213']
- kar67.jpeg: read ['KA12NOR9977']
- kar68.jpeg: read nothing
- kar69.jpeg: read ['KA19HO4016']
- kar70.jpeg: read nothing
- kar71.jpeg: read ['KA19MIY9272']
- kar75.jpeg: read nothing
- kar76.jpeg: read nothing
- kar8.jpg: read ['TN18O1868']
- kar81.jpeg: read ['KA28H7007']
- kar86.jpeg: read nothing
- kar87.jpeg: read ['KA42EB6653']
- kar89.jpeg: read nothing
- kar91.jpeg: read nothing
- kar93.jpeg: read ['GA03BO0943']
- kar95.jpeg: read ['KL14A9810']
- kar97.jpeg: read ['KA70IJ9934']
