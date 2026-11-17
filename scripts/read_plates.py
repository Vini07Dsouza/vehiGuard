"""Read the text on cropped plates with EasyOCR and report accuracy.

Plate rules come from config/plate_patterns.yaml via app.pipeline.plate_validator.
Run from the project folder:  python scripts/read_plates.py
"""

import re
import sys
from pathlib import Path

import cv2
import easyocr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # allow "python scripts/read_plates.py"

from app.pipeline.plate_validator import PlateValidator

CROPS = ROOT / "data/plate_crops"
ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
validator = PlateValidator()


def preprocess_variants(img):
    """Three versions of the crop; the best OCR result is kept."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    scale = max(1.0, 600 / gray.shape[1])
    big = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(big)
    _, otsu = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return [big, clahe, otsu]


def order_segments(results):
    """Sort text pieces top-to-bottom, then left-to-right (handles 2-line plates)."""
    items = []
    for box, text, conf in results:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((sum(ys) / 4, min(xs), max(ys) - min(ys), text, conf))
    if not items:
        return []
    avg_h = sum(i[2] for i in items) / len(items)
    items.sort(key=lambda i: i[0])
    rows, row = [], [items[0]]
    for item in items[1:]:
        if abs(item[0] - row[-1][0]) < 0.6 * avg_h:
            row.append(item)
        else:
            rows.append(row)
            row = [item]
    rows.append(row)
    ordered = []
    for r in rows:
        ordered += sorted(r, key=lambda i: i[1])
    return ordered


def read_plate(reader, img):
    best = ("", 0.0, "")  # plate, confidence, raw text
    best_valid = False
    for variant in preprocess_variants(img):
        results = order_segments(reader.readtext(variant, allowlist=ALLOWED))
        if not results:
            continue
        raw = re.sub(r"[^A-Z0-9]", "", "".join(r[3] for r in results).upper())
        conf = sum(r[4] for r in results) / len(results)
        checked = validator.validate(raw)
        valid = checked is not None
        plate = checked or raw  # show the raw text when it is not a valid plate
        if (valid, conf) > (best_valid, best[1]):
            best, best_valid = (plate, conf, raw), valid
    return best[0], best[1], best[2], best_valid


def main():
    reader = easyocr.Reader(["en"], gpu=False)
    total = valid_count = exact = named = 0
    for path in sorted(CROPS.glob("*.jpg")):
        img = cv2.imread(str(path))
        if img is None:
            continue
        plate, conf, raw, ok = read_plate(reader, img)
        m = re.match(r"[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}", path.stem)
        expected = m.group(0) if m else ""
        line = (
            f"{path.name:40} raw={raw:14} plate={plate:12} valid={ok} conf={conf:.2f}"
        )
        total += 1
        valid_count += ok
        if expected:
            named += 1
            exact += plate == expected
            line += f"  expected={expected} {'OK' if plate == expected else 'WRONG'}"
        print(line)
    print(f"\nCrops: {total}   Valid: {valid_count}   Exact match: {exact}/{named}")


if __name__ == "__main__":
    main()
