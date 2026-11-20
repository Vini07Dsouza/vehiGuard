"""Draft the answer key for the test photos: data/test_plates/plates.csv.

    python scripts/suggest_plate_labels.py [folder]

For every photo NOT already named after its plate, the detector + OCR make a
guess. YOU must then open plates.csv (Excel or VS Code) and check every row
against the photo:
  - plate column: the correct plate number (fix the guess if it is wrong)
  - write NONE if no readable plate is visible in the photo
  - leave plate empty to skip that photo for OCR scoring
The guess is only a starting point. An unchecked answer key would make the
OCR look better than it is. Existing rows are kept, so it is safe to re-run
after adding photos.
"""

import csv
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline.ocr import PlateReader
from app.pipeline.plate_detector import PlateDetector
from scripts.evaluate import IMAGE_TYPES, PLATE_IN_NAME

FIELDS = ["file", "plate", "ocr_guess", "checked"]


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/test_plates"
    out = folder / "plates.csv"
    rows = {}
    if out.exists():
        with open(out, newline="", encoding="utf-8") as f:
            rows = {r["file"]: r for r in csv.DictReader(f)}

    images = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES)
    todo = [p for p in images if not PLATE_IN_NAME.match(p.stem) and p.name not in rows]
    print(f"{len(images)} photos, {len(todo)} need a guess")
    detector, reader = PlateDetector(), PlateReader()
    for i, path in enumerate(todo, 1):
        img = cv2.imread(str(path))
        guess = ""
        if img is not None:
            reads = [reader.read(p.box.crop(img)) for p in detector.detect(img)]
            valid = sorted((r for r in reads if r.plate), key=lambda r: -r.confidence)
            guess = valid[0].plate if valid else ""
        rows[path.name] = {"file": path.name, "plate": guess, "ocr_guess": guess,
                           "checked": "no"}  # fmt: skip
        print(f"[{i}/{len(todo)}] {path.name}: {guess or '-'}", flush=True)

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for name in sorted(rows):
            writer.writerow({k: rows[name].get(k, "") for k in FIELDS})
    print(f"\nWrote {out.relative_to(ROOT)}. Now check every row against its photo,")
    print("fix the plate column, and set checked to yes.")


if __name__ == "__main__":
    main()
