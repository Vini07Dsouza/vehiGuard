"""Cut vehicle crops from the test photos and draft their labels (task 5.6).

    python scripts/suggest_appearance_labels.py [photo folder]

Writes crops to data/test_vehicles/ and a draft answer key
data/test_vehicles/vehicles.csv with columns:

  file         crop file name
  type         CAR, MOTORCYCLE, BUS or TRUCK   <- check this
  colour       WHITE_SILVER_GREY, BLACK, RED, BLUE, GREEN, YELLOW_ORANGE,
               BROWN or OTHER                  <- check this
  ai_type, ai_colour   what the system guessed (for comparison, do not edit)
  checked      change to yes once YOU have looked at the crop

Fix type and colour when they are wrong. If a crop is not a vehicle, or you
cannot tell the colour (dark, blurry, partly hidden), write UNKNOWN in the
colour column. UNKNOWN there means "the system should also say UNKNOWN".
Existing rows are kept, so it is safe to re-run after adding photos.
"""

import csv
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline.appearance import colour_family
from app.pipeline.plate_detector import PlateDetector
from app.pipeline.vehicle_detector import VehicleDetector

IMAGE_TYPES = {".jpg", ".jpeg", ".png"}
FIELDS = ["file", "type", "colour", "ai_type", "ai_colour", "checked"]
MAX_PER_PHOTO = 2  # the largest vehicles in a photo
MAX_SIDE = 1280


def main() -> None:
    photos = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/test_plates"
    out = ROOT / "data/test_vehicles"
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "vehicles.csv"
    rows = {}
    if csv_path.exists():
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            rows = {r["file"]: r for r in csv.DictReader(f)}

    vehicles, plates = VehicleDetector(), PlateDetector()
    images = sorted(p for p in photos.iterdir() if p.suffix.lower() in IMAGE_TYPES)
    added = 0
    for number, path in enumerate(images, 1):
        img = cv2.imread(str(path))
        if img is None:
            continue
        found = sorted(vehicles.detect(img), key=lambda d: -d.box.area)[:MAX_PER_PHOTO]
        plate_boxes = [p.box for p in plates.detect(img)]
        for i, det in enumerate(found):
            name = f"{path.stem}_v{i}.jpg".replace(" ", "_").replace("(", "").replace(")", "")  # fmt: skip
            if name in rows:
                continue
            crop = det.box.crop(img)
            inside = [b for b in plate_boxes
                      if det.box.contains_point(*b.centre)]  # fmt: skip
            plate = None
            if inside:
                b = inside[0]
                plate = (b.x1 - det.box.x1, b.y1 - det.box.y1,
                         b.x2 - det.box.x1, b.y2 - det.box.y1)  # fmt: skip
            guess = colour_family(crop, plate).family
            scale = MAX_SIDE / max(crop.shape[:2])
            if scale < 1:
                crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)  # fmt: skip
            cv2.imwrite(str(out / name), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
            rows[name] = {"file": name, "type": det.label,
                          "colour": guess if guess != "UNKNOWN" else "",
                          "ai_type": det.label, "ai_colour": guess,
                          "checked": "no"}  # fmt: skip
            added += 1
        print(
            f"[{number}/{len(images)}] {path.name}: {len(found)} vehicle(s)", flush=True
        )

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for name in sorted(rows):
            writer.writerow({k: rows[name].get(k, "") for k in FIELDS})
    print(f"\n{added} new crops, {len(rows)} in total -> {csv_path.relative_to(ROOT)}")
    print("Now open vehicles.csv, check every row against its crop, fix type and")
    print("colour, and set checked to yes. Then run scripts/evaluate_appearance.py")


if __name__ == "__main__":
    main()
