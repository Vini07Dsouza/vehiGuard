"""Day 2: detect number plates in photos and save the cropped plates."""

from pathlib import Path

import cv2
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

SRC = Path("data/test_plates")
CROPS = Path("data/plate_crops")
RESULTS = Path("data/plate_results")
CROPS.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)

weights = hf_hub_download(
    repo_id="krishnamishra8848/Nepal-Vehicle-License-Plate-Detection",
    filename="last.pt",
)
model = YOLO(weights)

EXTENSIONS = {".jpg", ".jpeg", ".png"}
images = [p for p in sorted(SRC.iterdir()) if p.suffix.lower() in EXTENSIONS]
print(f"Found {len(images)} photos in {SRC}")

for img_path in images:
    img = cv2.imread(str(img_path))
    result = model(img, conf=0.25, verbose=False)[0]
    print(f"{img_path.name}: {len(result.boxes)} plate(s) found")
    for i, box in enumerate(result.boxes):
        x1, y1, x2, y2 = (max(int(v), 0) for v in box.xyxy[0].tolist())
        cv2.imwrite(str(CROPS / f"{img_path.stem}_plate{i}.jpg"), img[y1:y2, x1:x2])
    cv2.imwrite(str(RESULTS / img_path.name), result.plot())
