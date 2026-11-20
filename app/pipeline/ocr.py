"""Read plate text: PaddleOCR first, EasyOCR as fallback (FR-PLT-04, task 2.6).

Engines load lazily (the first read takes a few seconds). Each engine is
tried on several preprocessed variants of the crop; the first valid plate
whose confidence passes the gate is returned at once (fast path), otherwise
the best valid reading from any engine/variant, otherwise the best raw text.
"""

import logging
import os
import re
from dataclasses import dataclass

import cv2
import numpy as np

from app.core.config import load_yaml
from app.pipeline import preprocess
from app.pipeline.plate_validator import PlateValidator

log = logging.getLogger(__name__)
ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
# Mobile models: much faster on a CPU than the default medium models
PADDLE_DET_MODEL = "PP-OCRv5_mobile_det"
PADDLE_REC_MODEL = "PP-OCRv5_mobile_rec"
TWO_LINE_MAX_RATIO = 2.2  # width/height below this looks like a two-line plate
# CPU threads for PaddleOCR; YOLO (PyTorch) gets the rest (see run.py)
OCR_THREADS = int(
    load_yaml("settings.yaml").get("performance", {}).get("ocr_threads", 3)
)


@dataclass(frozen=True)
class Segment:
    text: str
    conf: float
    box: list  # 4 corner points [[x, y], ...]


@dataclass(frozen=True)
class OcrResult:
    raw: str  # all text pieces joined in reading order
    plate: str | None  # validated plate, or None
    confidence: float
    engine: str
    variant: str


def order_segments(segments: list[Segment]) -> list[Segment]:
    """Top-to-bottom rows, then left-to-right (handles two-line plates)."""
    if not segments:
        return []
    items = []
    for s in segments:
        ys = [p[1] for p in s.box]
        items.append((sum(ys) / len(ys), min(p[0] for p in s.box), max(ys) - min(ys), s))  # fmt: skip
    avg_h = sum(i[2] for i in items) / len(items) or 1
    items.sort(key=lambda i: i[0])
    rows, row = [], [items[0]]
    for item in items[1:]:
        if abs(item[0] - row[-1][0]) < 0.6 * avg_h:
            row.append(item)
        else:
            rows.append(row)
            row = [item]
    rows.append(row)
    return [i[3] for r in rows for i in sorted(r, key=lambda i: i[1])]


class EasyOcrEngine:
    name = "easyocr"

    def __init__(self):
        import easyocr  # slow import, only when needed

        self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    def read(self, img: np.ndarray) -> list[Segment]:
        results = self.reader.readtext(img, allowlist=ALLOWED)
        return [Segment(t, float(c), [list(map(float, p)) for p in b]) for b, t, c in results]  # fmt: skip


class PaddleRecEngine:
    """PaddleOCR recognition only (no text detection): reads ONE line of text.

    About 30x faster than the full pipeline on a CPU, so it is the live
    default. Two-line plates are split into rows by PlateReader first.
    """

    name = "paddle_rec"
    single_line = True

    def __init__(self):
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import TextRecognition  # slow import, only when needed

        self.rec = TextRecognition(
            model_name=PADDLE_REC_MODEL, enable_mkldnn=False, cpu_threads=OCR_THREADS
        )

    def read(self, img: np.ndarray) -> list[Segment]:
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        res = self.rec.predict(img)[0]
        h, w = img.shape[:2]
        box = [[0, 0], [w, 0], [w, h], [0, h]]
        return [Segment(res["rec_text"], float(res["rec_score"]), box)]


class PaddleOcrEngine:
    """Full PaddleOCR: finds text lines, then reads them (slower, fallback)."""

    name = "paddleocr"

    def __init__(self):
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCR  # slow import, only when needed

        self.ocr = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_detection_model_name=PADDLE_DET_MODEL,
            text_recognition_model_name=PADDLE_REC_MODEL,
            enable_mkldnn=False,  # oneDNN crashes on Windows CPUs (Paddle 3)
            cpu_threads=OCR_THREADS,
        )

    def read(self, img: np.ndarray) -> list[Segment]:
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        res = self.ocr.predict(img)[0]
        return [
            Segment(t, float(c), np.asarray(p).tolist())
            for t, c, p in zip(
                res["rec_texts"], res["rec_scores"], res["rec_polys"], strict=False
            )
        ]


ENGINES = {
    "paddle_rec": PaddleRecEngine,
    "paddleocr": PaddleOcrEngine,
    "easyocr": EasyOcrEngine,
}


def split_rows(gray: np.ndarray) -> list[np.ndarray]:
    """Split a two-line plate into its top and bottom rows.

    Cuts at the row with the least ink in the middle band of the image.
    """
    h = gray.shape[0]
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    profile = ink.sum(axis=1)
    lo, hi = int(h * 0.35), int(h * 0.65)
    cut = lo + int(np.argmin(profile[lo:hi])) if hi > lo else h // 2
    return [gray[:cut], gray[cut:]]


class PlateReader:
    """Reads one plate crop with the configured engines and variants."""

    def __init__(
        self,
        engines: list[str] | None = None,
        variants: list[str] | None = None,
        conf_gate: float | None = None,
        validator: PlateValidator | None = None,
    ):
        cfg = load_yaml("settings.yaml")
        ocr_cfg = cfg.get("ocr", {})
        self.engine_names = engines or ocr_cfg.get("engines", ["paddleocr", "easyocr"])
        self.variant_names = variants or ocr_cfg.get("variants", ["gray", "full", "binary"])  # fmt: skip
        self.conf_gate = (
            cfg["pipeline"]["ocr_conf_gate"] if conf_gate is None else conf_gate
        )
        self.validator = validator or PlateValidator()
        self._engines: dict = {}

    def engine(self, name: str):
        if name not in self._engines:
            log.info("Loading OCR engine %s", name)
            try:
                self._engines[name] = ENGINES[name]()
            except Exception:  # an engine that fails to load is skipped
                log.exception("OCR engine %s could not be loaded", name)
                self._engines[name] = None
        return self._engines[name]

    def _result(self, segments, engine_name, variant) -> OcrResult:
        raw = re.sub(r"[^A-Z0-9]", "", "".join(s.text for s in segments).upper())
        conf = sum(s.conf for s in segments) / len(segments) if segments else 0.0
        return OcrResult(raw, self.validator.validate(raw), conf, engine_name, variant)

    def read_with(self, engine_name: str, img: np.ndarray, variant: str) -> OcrResult:
        engine = self.engine(engine_name)
        if engine is None:
            return OcrResult("", None, 0.0, engine_name, variant)
        if not getattr(engine, "single_line", False):
            return self._result(order_segments(engine.read(img)), engine_name, variant)

        # One-line reader: tall plates are read row by row first
        h, w = img.shape[:2]
        tall = w / max(h, 1) < TWO_LINE_MAX_RATIO
        attempts = ["rows", "whole"] if tall else ["whole", "rows"]
        best = None
        for attempt in attempts:
            if attempt == "whole":
                segments = engine.read(img)
            else:
                segments = [s for row in split_rows(img) for s in engine.read(row)]
            result = self._result(segments, engine_name, variant)
            if result.plate:
                return result
            if best is None or result.confidence > best.confidence:
                best = result
        return best

    def engines_for(self, crop: np.ndarray) -> list[str]:
        """Engine order for this crop.

        Two-line plates (tall crops, mostly two-wheelers) go to full PaddleOCR
        first: on the test photos it read 5 of 9 that the fast one-line reader
        got wrong (it adds the IND strip or hologram as an extra letter).
        """
        h, w = crop.shape[:2]
        names = list(self.engine_names)
        if w / max(h, 1) < TWO_LINE_MAX_RATIO and "paddleocr" in names:
            names.remove("paddleocr")
            names.insert(0, "paddleocr")
        return names

    def read(self, crop: np.ndarray, thorough: bool = True) -> OcrResult:
        """Read a plate crop.

        thorough=False (live): the first engine on the first variant; if that
        gives no valid plate, the second engine (full PaddleOCR) once.
        thorough=True: the first engine on every variant, then each fallback
        engine on the first variant, until a confident valid plate is found.
        """
        images = preprocess.variants(crop)
        engines = self.engines_for(crop)
        first_engine, first_variant = engines[0], self.variant_names[0]
        attempts = [(first_engine, first_variant)]
        if not thorough:
            attempts += [(e, first_variant) for e in engines[1:2]]
        else:
            attempts += [(first_engine, v) for v in self.variant_names[1:]]
            attempts += [(e, first_variant) for e in engines[1:]]
        best: OcrResult | None = None
        for engine_name, variant in attempts:
            result = self.read_with(engine_name, images[variant], variant)
            if result.plate and result.confidence >= self.conf_gate:
                return result  # good enough, stop early
            if best is None or (bool(result.plate), result.confidence) > (
                bool(best.plate),
                best.confidence,
            ):
                best = result
        return best or OcrResult("", None, 0.0, "none", "none")
