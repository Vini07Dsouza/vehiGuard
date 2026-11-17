"""Shared detection types and helpers."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def area(self) -> int:
        return max(self.width, 0) * max(self.height, 0)

    @property
    def centre(self) -> tuple[float, float]:
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2

    def contains_point(self, x: float, y: float) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def iou(self, other: "Box") -> float:
        ix1, iy1 = max(self.x1, other.x1), max(self.y1, other.y1)
        ix2, iy2 = min(self.x2, other.x2), min(self.y2, other.y2)
        inter = max(ix2 - ix1, 0) * max(iy2 - iy1, 0)
        union = self.area + other.area - inter
        return inter / union if union else 0.0

    def padded(self, frac_x: float, frac_y: float, width: int, height: int) -> "Box":
        """Grow by a fraction of the box size, clipped to the image."""
        px, py = int(frac_x * self.width), int(frac_y * self.height)
        return Box(
            max(self.x1 - px, 0),
            max(self.y1 - py, 0),
            min(self.x2 + px, width),
            min(self.y2 + py, height),
        )

    def crop(self, img: np.ndarray) -> np.ndarray:
        return img[self.y1 : self.y2, self.x1 : self.x2]


@dataclass(frozen=True)
class Detection:
    box: Box
    conf: float
    label: str  # e.g. "CAR", "MOTORCYCLE", "PLATE"
