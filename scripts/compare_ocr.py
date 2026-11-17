"""Compare OCR engines and preprocessing on the plate crops (tasks 2.5 and 2.6).

    python scripts/compare_ocr.py [crop folder]

Crops named after their plate (e.g. KA19AB1234_plate0.jpg) count towards
exact-match accuracy. Results are printed and saved to
docs/results/ocr_comparison.md for the report.
"""

import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline import preprocess
from app.pipeline.ocr import PlateReader

PLATE_IN_NAME = re.compile(r"^([A-Z]{2}\d{2}[A-Z]{1,3}\d{4}|\d{2}BH\d{4}[A-Z]{1,2})")
OUT = ROOT / "docs/results/ocr_comparison.md"
LABELS = {"gray": "no preprocessing", "full": "full preprocessing", "binary": "binarised"}  # fmt: skip


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/plate_crops"
    crops = sorted(p for p in folder.glob("*.jpg"))
    reader = PlateReader()
    stats = defaultdict(lambda: {"valid": 0, "exact": 0, "named": 0, "ms": 0.0})
    combined = {"valid": 0, "exact": 0, "named": 0, "ms": 0.0}

    for engine in reader.engine_names:  # load models before timing
        reader.engine(engine)

    for i, path in enumerate(crops, 1):
        img = cv2.imread(str(path))
        if img is None:
            continue
        m = PLATE_IN_NAME.match(path.stem)
        expected = m.group(1) if m else None
        images = preprocess.variants(img)
        for engine in reader.engine_names:
            for variant in reader.variant_names:
                t0 = time.perf_counter()
                r = reader.read_with(engine, images[variant], variant)
                s = stats[(engine, variant)]
                s["ms"] += (time.perf_counter() - t0) * 1000
                s["valid"] += r.plate is not None
                if expected:
                    s["named"] += 1
                    s["exact"] += r.plate == expected
        t0 = time.perf_counter()
        r = reader.read(img)  # what the pipeline actually uses
        combined["ms"] += (time.perf_counter() - t0) * 1000
        combined["valid"] += r.plate is not None
        if expected:
            combined["named"] += 1
            combined["exact"] += r.plate == expected
        print(
            f"[{i}/{len(crops)}] {path.name}: {r.plate or '-'} ({r.engine}/{r.variant})"
        )

    n = len(crops)
    rows = [
        "| Engine | Input | Valid plates | Exact (named) | ms per crop |",
        "|---|---|---|---|---|",
    ]
    for (engine, variant), s in stats.items():
        rows.append(
            f"| {engine} | {LABELS[variant]} | {s['valid']}/{n} "
            f"({100 * s['valid'] / n:.0f}%) | {s['exact']}/{s['named']} "
            f"| {s['ms'] / n:.0f} |"
        )
    c = combined
    rows.append(
        f"| **Pipeline (PlateReader)** | best of the above, early stop "
        f"| **{c['valid']}/{n} ({100 * c['valid'] / n:.0f}%)** "
        f"| **{c['exact']}/{c['named']}** | **{c['ms'] / n:.0f}** |"
    )
    table = "\n".join(rows)
    print("\n" + table)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        f"# OCR comparison (tasks 2.5 and 2.6)\n\n"
        f"Run on {datetime.now().astimezone().date()} with `python scripts/compare_ocr.py` on "
        f"{n} plate crops from `{folder.relative_to(ROOT).as_posix()}` "
        f'(CPU only). "Valid" means the text passed the Indian plate rules; '
        f'"Exact" counts only crops named after their plate.\n\n{table}\n',
        encoding="utf-8",
    )
    print(f"\nSaved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
