"""Vehicle colour family from a vehicle crop (FR-APP-02/05, tasks 5.2 and 5.3).

Steps (architecture §8.2):
  1. take the middle of the vehicle box (body, not road or sky) and hide the
     plate area
  2. convert to HSV and give every pixel a colour family
  3. the family with the most pixels wins, if it clearly wins
  4. too small, too dark, too bright, too blurred or too mixed -> UNKNOWN

UNKNOWN is a normal answer, never a guess: it never causes a mismatch.
Thresholds are in config/settings.yaml (appearance section).
"""

from collections import Counter
from dataclasses import dataclass

import cv2
import numpy as np

from app.core.config import load_yaml
from app.domain.states import ColourFamily

F = ColourFamily
ANALYSIS_SIZE = 160  # longest side the crop is shrunk to (speed)


@dataclass(frozen=True)
class AppearanceConfig:
    min_width_px: int = 60  # smaller vehicle crops are UNKNOWN
    min_height_px: int = 40
    min_mean_value: float = 35  # darker than this: too dark to judge (night)
    max_mean_value: float = 245  # brighter than this: overexposed
    min_sharpness: float = 8.0  # variance of the Laplacian; lower = too blurred
    min_dominant_share: float = 0.40  # the winning family needs this share
    low_saturation: int = 50  # below this a pixel is grey, white or black
    black_max_value: int = 80  # grey pixels darker than this are black
    body_margin: float = 0.18  # share cut from each side of the box

    @classmethod
    def from_settings(cls) -> "AppearanceConfig":
        return cls(**load_yaml("settings.yaml").get("appearance", {}))


def body_region(
    vehicle: np.ndarray, plate_box: tuple[int, int, int, int] | None, margin: float
) -> tuple[np.ndarray, np.ndarray]:
    """The middle of the vehicle crop and a mask that hides the plate."""
    h, w = vehicle.shape[:2]
    mask = np.full((h, w), 255, np.uint8)
    if plate_box:  # plate box in vehicle-crop pixel coordinates
        x1, y1, x2, y2 = plate_box
        pad_x, pad_y = int((x2 - x1) * 0.15), int((y2 - y1) * 0.3)
        mask[max(y1 - pad_y, 0) : y2 + pad_y, max(x1 - pad_x, 0) : x2 + pad_x] = 0
    mx, my = int(w * margin), int(h * margin)
    return vehicle[my : h - my, mx : w - mx], mask[my : h - my, mx : w - mx]


def classify_pixels(hsv: np.ndarray, cfg: AppearanceConfig) -> np.ndarray:
    """Colour family number for every pixel (index into FAMILIES)."""
    hue = hsv[..., 0].astype(np.int32)  # OpenCV hue is 0-179
    sat = hsv[..., 1].astype(np.int32)
    val = hsv[..., 2].astype(np.int32)
    out = np.full(hue.shape, FAMILIES.index(F.OTHER), np.uint8)

    grey = sat < cfg.low_saturation
    out[grey & (val < cfg.black_max_value)] = FAMILIES.index(F.BLACK)
    out[grey & (val >= cfg.black_max_value)] = FAMILIES.index(F.WHITE_SILVER_GREY)
    out[~grey & (val < 45)] = FAMILIES.index(F.BLACK)  # very dark, any hue

    coloured = ~grey & (val >= 45)
    out[coloured & ((hue < 8) | (hue >= 170))] = FAMILIES.index(F.RED)
    warm = coloured & (hue >= 8) & (hue < 35)
    out[warm & (val >= 150)] = FAMILIES.index(F.YELLOW_ORANGE)
    out[warm & (val < 150)] = FAMILIES.index(F.BROWN)  # dark orange is brown
    out[coloured & (hue >= 35) & (hue < 85)] = FAMILIES.index(F.GREEN)
    out[coloured & (hue >= 85) & (hue < 130)] = FAMILIES.index(F.BLUE)
    return out  # hues 130-170 (purple, pink) stay OTHER


# Order of the numbers used in classify_pixels (UNKNOWN is never a pixel class)
FAMILIES = [
    F.WHITE_SILVER_GREY,
    F.BLACK,
    F.RED,
    F.BLUE,
    F.GREEN,
    F.YELLOW_ORANGE,
    F.BROWN,
    F.OTHER,
]


@dataclass(frozen=True)
class ColourReading:
    family: ColourFamily
    share: float  # how much of the body the winning family covers (0-1)
    reason: str  # why UNKNOWN, or "ok"


def unknown(reason: str, share: float = 0.0) -> ColourReading:
    return ColourReading(F.UNKNOWN, share, reason)


def colour_family(
    vehicle: np.ndarray,
    plate_box: tuple[int, int, int, int] | None = None,
    cfg: AppearanceConfig | None = None,
) -> ColourReading:
    """Colour family of one vehicle crop (BGR image), or UNKNOWN."""
    cfg = cfg or AppearanceConfig.from_settings()
    if vehicle is None or vehicle.size == 0:
        return unknown("empty")
    h, w = vehicle.shape[:2]
    if w < cfg.min_width_px or h < cfg.min_height_px:
        return unknown("too_small")

    scale = ANALYSIS_SIZE / max(h, w)
    if scale < 1:
        vehicle = cv2.resize(vehicle, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)  # fmt: skip
        if plate_box:
            plate_box = tuple(int(v * scale) for v in plate_box)
    body, mask = body_region(vehicle, plate_box, cfg.body_margin)
    if body.size == 0 or not mask.any():
        return unknown("too_small")

    hsv = cv2.cvtColor(body, cv2.COLOR_BGR2HSV)
    visible = mask > 0
    mean_value = float(hsv[..., 2][visible].mean())
    if mean_value < cfg.min_mean_value:
        return unknown("too_dark")
    if mean_value > cfg.max_mean_value:
        return unknown("overexposed")
    gray = cv2.cvtColor(body, cv2.COLOR_BGR2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < cfg.min_sharpness:
        return unknown("blurred")

    labels = classify_pixels(hsv, cfg)[visible]
    counts = Counter(labels.tolist())
    index, count = counts.most_common(1)[0]
    share = count / labels.size
    if share < cfg.min_dominant_share:
        return unknown("mixed_colours", share)
    return ColourReading(FAMILIES[index], share, "ok")
