"""Day 3: read the text on cropped plates with EasyOCR."""

import re
from pathlib import Path

import cv2
import easyocr

CROPS = Path("data/plate_crops")
ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

STANDARD = re.compile(r"^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$")
BH_SERIES = re.compile(r"\d{2}BH\d{4}[A-Z]{1,2}")
STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "DN", "GA", "GJ", "HP",
    "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL",
    "OD", "OR", "PB", "PY", "RJ", "SK", "TN", "TR", "TS", "UK", "UP", "WB",
}  # fmt: skip
TO_DIGIT = {
    "O": "0",
    "Q": "0",
    "D": "0",
    "I": "1",
    "L": "1",
    "T": "1",
    "Z": "2",
    "S": "5",
    "B": "8",
    "G": "6",
}
TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}


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


def fix_window(window):
    """Letters in the state/series slots, digits in the number slots."""
    n = len(window)
    out = []
    for i, ch in enumerate(window):
        if i < 2 or 4 <= i < n - 4:
            out.append(TO_LETTER.get(ch, ch))
        else:
            out.append(TO_DIGIT.get(ch, ch))
    return "".join(out)


def extract_plate(text):
    # Blue "IND" strip on HSRP plates: may be read first or between the two rows
    text = re.sub(r"^[A-Z0-9]?ND", "", text).replace("IND", "")
    bh = BH_SERIES.search(text)
    if bh:
        return bh.group(0)
    for n in (10, 9, 11):
        for start in range(len(text) - n + 1):
            window = fix_window(text[start : start + n])
            if STANDARD.match(window) and window[:2] in STATE_CODES:
                return window
    return text


def is_valid(plate):
    if BH_SERIES.fullmatch(plate):
        return True
    return bool(STANDARD.match(plate)) and plate[:2] in STATE_CODES


def read_plate(reader, img):
    best = ("", 0.0, "")  # plate, confidence, raw text
    best_valid = False
    for variant in preprocess_variants(img):
        results = order_segments(reader.readtext(variant, allowlist=ALLOWED))
        if not results:
            continue
        raw = re.sub(r"[^A-Z0-9]", "", "".join(r[3] for r in results).upper())
        conf = sum(r[4] for r in results) / len(results)
        plate = extract_plate(raw)
        valid = is_valid(plate)
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
