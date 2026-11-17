"""Prepare a plate crop for OCR (FR-PLT-03, task 2.5).

Steps: upscale small crops, grayscale, denoise, contrast boost (CLAHE) and
deskew. OCR runs on a few variants and keeps the best valid reading, because
no single variant wins on every plate.
"""

import cv2
import numpy as np

TARGET_WIDTH = 600  # OCR works better on plates at least this wide
MAX_DESKEW_DEG = 20  # ignore angles larger than this (probably not a tilt)


def to_gray(img: np.ndarray) -> np.ndarray:
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def upscale(gray: np.ndarray, target_width: int = TARGET_WIDTH) -> np.ndarray:
    scale = target_width / gray.shape[1]
    if scale <= 1:
        return gray
    return cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def denoise(gray: np.ndarray) -> np.ndarray:
    # Edge-preserving smoothing: removes grain but keeps character edges sharp
    return cv2.bilateralFilter(gray, 7, 50, 50)


def enhance_contrast(gray: np.ndarray) -> np.ndarray:
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)


def estimate_skew(gray: np.ndarray) -> float:
    """Angle (degrees) of the dominant near-horizontal lines, 0 if unsure."""
    edges = cv2.Canny(gray, 50, 150)
    min_len = gray.shape[1] // 3
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 80, minLineLength=min_len, maxLineGap=10)  # fmt: skip
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines[:, 0]:
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if abs(angle) <= MAX_DESKEW_DEG:
            angles.append(angle)
    return float(np.median(angles)) if angles else 0.0


def deskew(gray: np.ndarray, angle: float | None = None) -> np.ndarray:
    angle = estimate_skew(gray) if angle is None else angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def preprocess(img: np.ndarray) -> np.ndarray:
    """The full chain from FR-PLT-03."""
    gray = upscale(to_gray(img))
    return enhance_contrast(deskew(denoise(gray)))


def variants(img: np.ndarray) -> dict[str, np.ndarray]:
    """Versions of the crop to try with OCR (the best valid reading wins)."""
    gray = upscale(to_gray(img))
    full = enhance_contrast(deskew(denoise(gray)))
    _, binary = cv2.threshold(full, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return {"gray": gray, "full": full, "binary": binary}
