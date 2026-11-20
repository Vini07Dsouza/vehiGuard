"""Score vehicle type and colour against your checked answers (tasks 5.6/5.7).

    python scripts/evaluate_appearance.py

Reads data/test_vehicles/vehicles.csv (rows with checked = yes). Type is the
detector class from the full photo (ai_type); colour is recomputed from the
crop with the current settings, so you can tune config/settings.yaml
(appearance section) and run this again.

Results are saved to docs/results/appearance_evaluation.md. Targets from the
PRD (NFR-ACC-03): type >= 90%, colour family >= 80%.
"""

import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.pipeline.appearance import colour_family
from app.pipeline.plate_detector import PlateDetector

CROPS = ROOT / "data/test_vehicles"
TARGET_TYPE, TARGET_COLOUR = 0.90, 0.80
FAMILIES = ["WHITE_SILVER_GREY", "BLACK", "RED", "BLUE", "GREEN", "YELLOW_ORANGE", "BROWN", "OTHER", "UNKNOWN"]  # fmt: skip


def pct(n: int, total: int) -> str:
    return f"{n}/{total} = **{n / total:.0%}**" if total else "n/a"


def main() -> None:
    with open(CROPS / "vehicles.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    checked = [r for r in rows if r["checked"].strip().lower() in ("yes", "y")]
    if not checked:
        raise SystemExit("No rows are marked checked = yes in vehicles.csv yet.")
    plates = PlateDetector()

    type_ok = type_n = 0
    col_ok = col_n = col_unknown = answered_ok = answered = 0
    unknown_truth_ok = unknown_truth_n = 0
    confusion: Counter = Counter()
    wrong = []
    for r in checked:
        truth_type = r["type"].strip().upper()
        truth_col = r["colour"].strip().upper()
        if truth_type in ("CAR", "MOTORCYCLE", "BUS", "TRUCK"):
            type_n += 1
            type_ok += r["ai_type"].strip().upper() == truth_type
            if r["ai_type"].strip().upper() != truth_type:
                wrong.append(f"{r['file']}: type {r['ai_type']} (truth {truth_type})")
        if truth_col not in FAMILIES:
            continue
        crop = cv2.imread(str(CROPS / r["file"]))
        if crop is None:
            continue
        plate = None
        boxes = plates.detect(crop)
        if boxes:
            b = boxes[0].box
            plate = (b.x1, b.y1, b.x2, b.y2)
        guess = colour_family(crop, plate).family.value
        if truth_col == "UNKNOWN":  # the right answer is "cannot tell"
            unknown_truth_n += 1
            unknown_truth_ok += guess == "UNKNOWN"
            continue
        col_n += 1
        col_ok += guess == truth_col
        col_unknown += guess == "UNKNOWN"
        if guess != "UNKNOWN":
            answered += 1
            answered_ok += guess == truth_col
        if guess != truth_col:
            confusion[(truth_col, guess)] += 1
            wrong.append(f"{r['file']}: colour {guess} (truth {truth_col})")

    type_rate = type_ok / type_n if type_n else 0
    col_rate = col_ok / col_n if col_n else 0
    confusions = "\n".join(
        f"- {t} read as {g}: {n}" for (t, g), n in confusion.most_common(12)
    )
    report = (
        f"# Appearance evaluation (tasks 5.6 and 5.7)\n\n"
        f"Run on {datetime.now().astimezone():%Y-%m-%d %H:%M} with "
        f"`python scripts/evaluate_appearance.py`. {len(checked)} checked crops "
        f"from `data/test_vehicles/`. CPU only.\n\n"
        "| Metric | Result | Target | Status |\n|---|---|---|---|\n"
        f"| Vehicle type accuracy | {pct(type_ok, type_n)} | ≥ {TARGET_TYPE:.0%} | "
        f"{'PASS' if type_rate >= TARGET_TYPE else 'below target'} |\n"
        f"| Colour family accuracy (UNKNOWN counts as wrong) | {pct(col_ok, col_n)} | "
        f"≥ {TARGET_COLOUR:.0%} | "
        f"{'PASS' if col_rate >= TARGET_COLOUR else 'below target'} |\n"
        f"| Colour accuracy when the system gave an answer | "
        f"{pct(answered_ok, answered)} | — | — |\n"
        f"| Colour answered UNKNOWN | {pct(col_unknown, col_n)} | — | — |\n"
        f"| Crops you marked UNKNOWN that the system also called UNKNOWN | "
        f"{pct(unknown_truth_ok, unknown_truth_n)} | — | — |\n\n"
        "UNKNOWN is never a mismatch, so a high UNKNOWN rate costs missed "
        "signals, not false alarms.\n\n"
        f"## Most common colour mix-ups\n\n{confusions or '(none)'}\n\n"
        "## Wrong or unclear crops\n\n" + "\n".join(f"- {w}" for w in wrong) + "\n"
    )
    print(report)
    out = ROOT / "docs/results/appearance_evaluation.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"Saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
