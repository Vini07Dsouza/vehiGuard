"""Day 3: read the text on cropped plates with EasyOCR."""

import re
from pathlib import Path

import cv2
import easyocr

CROPS = Path("data/plate_crops")
ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# Indian formats: KA19AB1234 (standard) and 22BH1234AA (BH series)
STANDARD = re.compile(r"^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{4}$")
BH_SERIES = re.compile(r"^\d{2}BH\d{4}[A-Z]{1,2}$")

# Common OCR confusions
TO_DIGIT = {
    "O": "0",
    "Q": "0",
    "D": "0",
    "I": "1",
    "L": "1",
    "Z": "2",
    "S": "5",
    "B": "8",
    "G": "6",
}
TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}


def preprocess(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def clean(text):
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def fix_plate(text):
    """Fix letter/digit mix-ups by position for plates like KA19AB1234."""
    if not 9 <= len(text) <= 10:
        return text
    chars = list(text)
    for i in (0, 1):  # state code = letters
        chars[i] = TO_LETTER.get(chars[i], chars[i])
    n = len(chars)
    for i in (2, n - 4, n - 3, n - 2, n - 1):  # RTO digit and last 4 = digits
        chars[i] = TO_DIGIT.get(chars[i], chars[i])
    return "".join(chars)


def is_valid(text):
    return bool(STANDARD.match(text) or BH_SERIES.match(text))


def read_plate(reader, img):
    results = reader.readtext(preprocess(img), allowlist=ALLOWED)
    results.sort(key=lambda r: r[0][0][0])  # left to right
    if not results:
        return "", 0.0
    text = "".join(r[1] for r in results)
    conf = sum(r[2] for r in results) / len(results)
    return clean(text), conf


def main():
    reader = easyocr.Reader(["en"], gpu=False)
    files = sorted(CROPS.glob("*.jpg"))
    total = valid = exact = named = 0
    for path in files:
        img = cv2.imread(str(path))
        raw, conf = read_plate(reader, img)
        plate = fix_plate(raw)
        ok = is_valid(plate)
        match = re.match(r"[A-Z0-9]+", path.stem)
        expected = match.group(0) if match else ""
        line = (
            f"{path.name:35} raw={raw:12} fixed={plate:12} valid={ok} conf={conf:.2f}"
        )
        total += 1
        valid += ok
        if STANDARD.match(expected):  # file named like KA19AB1234_01_plate0.jpg
            named += 1
            exact += plate == expected
            line += f" expected={expected} {'OK' if plate == expected else 'WRONG'}"
        print(line)
    print(f"\nCrops: {total}   Valid format: {valid}   Exact match: {exact}/{named}")


if __name__ == "__main__":
    main()
