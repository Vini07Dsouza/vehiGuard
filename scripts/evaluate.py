"""Offline evaluation of plate detection and OCR (task 2.10, metrics M1/M2).

    python scripts/evaluate.py                         # data/test_plates
    python scripts/evaluate.py data/plate_test --labels data/plate_test/labels
    python scripts/evaluate.py --weights models/plate_detector.pt   # your model

Images are named after their plate (e.g. KA19AB1234.jpg, KA19AB1234_2.png);
other names count for detection only. With --labels (YOLO .txt files from
Roboflow, same file name) detection is scored by box overlap (IoU >= 0.5);
without labels an image counts as detected when at least one plate is found.

Results are saved to docs/results/plate_evaluation[_<name>].md.
"""

import argparse
import csv
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline.detection import Box
from app.pipeline.ocr import PlateReader
from app.pipeline.plate_detector import PlateDetector

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp"}
PLATE_IN_NAME = re.compile(r"^([A-Z]{2}\d{2}[A-Z]{1,3}\d{4}|\d{2}BH\d{4}[A-Z]{1,2})")
TARGET_RECALL, TARGET_EXACT = 0.90, 0.85


def yolo_boxes(label_file: Path, width: int, height: int) -> list[Box]:
    boxes = []
    if not label_file.exists():
        return boxes
    for line in label_file.read_text().splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        _, cx, cy, w, h = map(float, parts[:5])
        boxes.append(
            Box(
                int((cx - w / 2) * width),
                int((cy - h / 2) * height),
                int((cx + w / 2) * width),
                int((cy + h / 2) * height),
            )
        )
    return boxes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default="data/test_plates")
    parser.add_argument("--labels", help="folder with YOLO .txt labels")
    parser.add_argument("--weights", help="plate model (default: settings.yaml)")
    parser.add_argument("--name", default="", help="suffix for the results file")
    parser.add_argument(
        "--include-unchecked",
        action="store_true",
        help="also use plates.csv rows not marked checked=yes (preview only)",
    )
    parser.add_argument("--conf", type=float, help="plate detector confidence cut-off")
    parser.add_argument(
        "--fast-ocr",
        action="store_true",
        help="live-pipeline OCR (fast path) instead of the thorough one",
    )
    parser.add_argument(
        "--detection-only", action="store_true", help="skip OCR (fast, about 1 minute)"
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    folder = folder if folder.is_absolute() else ROOT / folder
    labels = Path(args.labels) if args.labels else None
    if labels and not labels.is_absolute():
        labels = ROOT / labels
    images = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES)
    key, unchecked = answer_key(folder, args.include_unchecked)
    detector = PlateDetector(weights=args.weights, conf=args.conf)
    reader = None if args.detection_only else PlateReader()

    gt_total = gt_found = pred_total = pred_correct = 0
    img_detected = named = exact = no_plate_images = false_reads = 0
    det_ms = ocr_ms = 0.0
    wrong = []
    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            continue
        h, w = img.shape[:2]
        t = time.perf_counter()
        plates = detector.detect(img)
        det_ms += (time.perf_counter() - t) * 1000
        m = PLATE_IN_NAME.match(path.stem)
        expected = m.group(1) if m else key.get(path.name)

        if expected == "NONE" and reader is None:
            no_plate_images += 1
            print(f"{path.name}: (no plate) {len(plates)} box(es)")
            continue
        if expected == "NONE":  # no plate in the photo: any valid read is wrong
            no_plate_images += 1
            reads = [
                reader.read(p.box.crop(img), thorough=not args.fast_ocr).plate
                for p in plates
            ]
            if any(reads):
                false_reads += 1
                wrong.append(
                    f"{path.name}: no plate, but read {[r for r in reads if r]}"
                )
            print(f"{path.name}: (no plate) {len(plates)} box(es)")
            continue
        img_detected += bool(plates)

        if labels:
            gt = yolo_boxes(labels / f"{path.stem}.txt", w, h)
            gt_total += len(gt)
            pred_total += len(plates)
            gt_found += sum(any(g.iou(p.box) >= 0.5 for p in plates) for g in gt)
            pred_correct += sum(any(p.box.iou(g) >= 0.5 for g in gt) for p in plates)

        if expected and reader is not None:
            named += 1
            t = time.perf_counter()
            reads = [
                reader.read(p.box.crop(img), thorough=not args.fast_ocr).plate
                for p in plates
            ]
            ocr_ms += (time.perf_counter() - t) * 1000
            if expected in reads:
                exact += 1
            else:
                wrong.append(
                    f"{path.name}: read {[r for r in reads if r] or 'nothing'}"
                )
        print(f"{path.name}: {len(plates)} plate(s)")

    n = max(len(images) - no_plate_images, 1)  # photos that contain a plate
    if labels:
        recall = gt_found / max(gt_total, 1)
        precision = pred_correct / max(pred_total, 1)
        det_line = (
            f"| Detection recall (IoU ≥ 0.5) | {gt_found}/{gt_total} = "
            f"**{recall:.0%}** | ≥ {TARGET_RECALL:.0%} | "
            f"{'PASS' if recall >= TARGET_RECALL else 'below target'} |\n"
            f"| Detection precision | {pred_correct}/{pred_total} = {precision:.0%} | — | — |"
        )
    else:
        recall = img_detected / n
        det_line = (
            f"| Images with a plate found (no labels) | {img_detected}/{n} = "
            f"**{recall:.0%}** | ≥ {TARGET_RECALL:.0%} | "
            f"{'PASS' if recall >= TARGET_RECALL else 'below target'} |"
        )
    exact_rate = exact / max(named, 1)
    model = args.weights or "settings.yaml detection.plate_model"
    report = (
        f"# Plate evaluation{' — ' + args.name if args.name else ''}\n\n"
        f"Run on {datetime.now().astimezone():%Y-%m-%d %H:%M} with "
        f"`python scripts/evaluate.py`. Folder: `{path_text(folder)}`, "
        f"{len(images)} images. Plate model: `{model}`. CPU only.\n\n"
        "| Metric | Result | Target | Status |\n|---|---|---|---|\n"
        f"{det_line}\n"
        f"| OCR exact match (single image, known plates) | {exact}/{named} = "
        f"**{exact_rate:.0%}** | ≥ {TARGET_EXACT:.0%} | "
        f"{'PASS' if exact_rate >= TARGET_EXACT else 'below target'} |\n"
        f"| Photos without a plate where a plate was wrongly read | "
        f"{false_reads}/{no_plate_images} | 0 | "
        f"{'PASS' if false_reads == 0 else 'check'} |\n"
        f"| Plate detection time | {det_ms / max(len(images), 1):.0f} ms per image "
        f"| — | — |\n"
        f"| OCR time | {ocr_ms / max(named, 1):.0f} ms per image | — | — |\n\n"
        "Known plates come from file names and checked rows of `plates.csv`"
        f"{f'; {unchecked} unchecked rows were skipped' if unchecked else ''}. "
        "Single-image OCR is stricter than the live pipeline, which votes over "
        "several frames.\n\n"
        "## Missed or wrong reads\n\n" + "\n".join(f"- {w}" for w in wrong) + "\n"
    )
    print("\n" + report)
    out = (
        ROOT
        / "docs/results"
        / (f"plate_evaluation{'_' + args.name if args.name else ''}.md")
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"Saved {out.relative_to(ROOT)}")


def answer_key(folder: Path, include_unchecked: bool) -> tuple[dict[str, str], int]:
    """Plates from plates.csv: {file: plate or "NONE"}, and unchecked count."""
    path = folder / "plates.csv"
    if not path.exists():
        return {}, 0
    key, unchecked = {}, 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            plate = re.sub(r"[^A-Z0-9]", "", (row.get("plate") or "").upper())
            if not plate:
                continue
            if row.get("checked", "").strip().lower() not in ("yes", "y"):
                unchecked += 1
                if not include_unchecked:
                    continue
            key[row["file"]] = plate
    return key, unchecked


def path_text(p: Path) -> str:
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else str(p)


if __name__ == "__main__":
    main()
