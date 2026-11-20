"""Pack labelled plate photos into a YOLO training set and a zip for Colab (task 2.4).

    python scripts/make_yolo_dataset.py <images> <labels> <output folder> [--val 0.2]

Creates <output>/train/{images,labels}, <output>/valid/{images,labels},
<output>/data.yaml and <output>.zip. The split is random but repeatable
(fixed seed). Photos without a label file are skipped.

Keep your own test photos (data/test_plates) OUT of this set, so the trained
model is judged on photos it has never seen.
"""

import argparse
import random
import shutil
from pathlib import Path

import cv2

IMAGE_TYPES = {".jpg", ".jpeg", ".png"}


def save_resized(src: Path, dst: Path, max_size: int) -> None:
    """Copy a photo, shrinking it so its longest side is at most max_size."""
    img = cv2.imread(str(src))
    scale = max_size / max(img.shape[:2])
    if scale < 1:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(dst), img, [cv2.IMWRITE_JPEG_QUALITY, 92])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("images")
    parser.add_argument("labels")
    parser.add_argument("output")
    parser.add_argument("--val", type=float, default=0.2, help="share for validation")
    parser.add_argument(
        "--max-size", type=int, default=1280, help="longest image side in pixels"
    )
    args = parser.parse_args()

    images = Path(args.images)
    labels = Path(args.labels)
    out = Path(args.output)
    pairs = sorted(
        (img, labels / f"{img.stem}.txt")
        for img in images.iterdir()
        if img.suffix.lower() in IMAGE_TYPES and (labels / f"{img.stem}.txt").exists()
    )
    if not pairs:
        raise SystemExit("No photo has a matching label file")
    random.Random(42).shuffle(pairs)
    n_val = max(1, round(len(pairs) * args.val))
    splits = {"valid": pairs[:n_val], "train": pairs[n_val:]}

    if out.exists():
        shutil.rmtree(out)
    for split, items in splits.items():
        for sub in ("images", "labels"):
            (out / split / sub).mkdir(parents=True)
        for img, label in items:
            save_resized(img, out / split / "images" / img.name, args.max_size)
            # labels are fractions of the image size, so resizing keeps them right
            shutil.copy2(label, out / split / "labels" / label.name)
    (out / "data.yaml").write_text(
        "# Paths are relative to this file (works on Colab after unzipping)\n"
        f"path: {out.name}\n"
        "train: train/images\n"
        "val: valid/images\n"
        "nc: 1\n"
        "names: ['plate']\n",
        encoding="utf-8",
    )
    archive = shutil.make_archive(
        str(out), "zip", root_dir=out.parent, base_dir=out.name
    )
    print(
        f"train {len(splits['train'])}, valid {len(splits['valid'])} photos -> {out}\n"
        f"Upload this file to Colab: {archive}"
    )


if __name__ == "__main__":
    main()
