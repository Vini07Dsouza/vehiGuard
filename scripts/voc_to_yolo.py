"""Convert Pascal VOC XML plate labels to YOLO format (for evaluate.py / training).

    python scripts/voc_to_yolo.py <images folder> <xml folder> <output folder>

Writes <output>/images/*.jpg (copies) and <output>/labels/*.txt, one line per
plate: "0 cx cy w h" (normalised 0-1). Plate texts, when the XML has them, go
to <output>/plates.csv for reference.
"""

import csv
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def convert(images: Path, xmls: Path, out: Path) -> tuple[int, int]:
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(parents=True, exist_ok=True)
    texts = []
    n_images = n_boxes = 0
    for xml_path in sorted(xmls.glob("*.xml")):
        root = ET.parse(xml_path).getroot()
        image = images / root.findtext("filename", "")
        if not image.exists():
            image = images / f"{xml_path.stem}.jpg"
        if not image.exists():
            print(f"skip {xml_path.name}: image not found")
            continue
        w = float(root.findtext("size/width"))
        h = float(root.findtext("size/height"))
        lines = []
        for obj in root.iter("object"):
            box = obj.find("bndbox")
            x1, y1, x2, y2 = (float(box.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))  # fmt: skip
            lines.append(
                f"0 {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} "
                f"{(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}"
            )
            for attr in obj.iter("attribute"):
                if attr.findtext("name") == "number_plate_text":
                    texts.append({"file": image.name, "plate_text": attr.findtext("value")})  # fmt: skip
        safe = image.name.replace(" ", "_").replace("(", "").replace(")", "")
        shutil.copy2(image, out / "images" / safe)
        (out / "labels" / f"{Path(safe).stem}.txt").write_text("\n".join(lines) + "\n")
        n_images += 1
        n_boxes += len(lines)
    if texts:
        with open(out / "plates.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file", "plate_text"])
            writer.writeheader()
            writer.writerows(texts)
    return n_images, n_boxes


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    imgs, boxes = convert(*(Path(a) for a in sys.argv[1:]))
    print(f"{imgs} images, {boxes} plate boxes -> {sys.argv[3]}")
