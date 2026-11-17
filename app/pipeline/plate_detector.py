"""Find number plates and crop them with a margin (FR-PLT-02, task 2.2).

The model is set in config/settings.yaml (detection.plate_model):
  - "hf://<repo>/<file>"  downloads from Hugging Face (the Nepal baseline, D07)
  - a local path, e.g. "models/plate_detector.pt" (your fine-tuned model, 2.4)
"""

from huggingface_hub import hf_hub_download
from ultralytics import YOLO

from app.core.config import ROOT_DIR, load_yaml
from app.pipeline.detection import Box, Detection

# Margin around a plate box, so OCR sees the whole plate (fraction of size)
PAD_X, PAD_Y = 0.08, 0.15


def resolve_weights(spec: str) -> str:
    if spec.startswith("hf://"):
        repo, _, filename = spec.removeprefix("hf://").rpartition("/")
        return hf_hub_download(repo_id=repo, filename=filename)
    return str(ROOT_DIR / spec)


class PlateDetector:
    def __init__(self, weights: str | None = None, conf: float | None = None):
        cfg = load_yaml("settings.yaml")["detection"]
        self.model = YOLO(resolve_weights(weights or cfg["plate_model"]))
        self.conf = conf if conf is not None else cfg["plate_conf"]
        self.imgsz = cfg["plate_imgsz"]

    def detect(self, frame) -> list[Detection]:
        h, w = frame.shape[:2]
        result = self.model(frame, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
        found = []
        for xyxy, conf in zip(
            result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), strict=True
        ):
            box = Box(*(int(v) for v in xyxy)).padded(PAD_X, PAD_Y, w, h)
            found.append(Detection(box, float(conf), "PLATE"))
        return found
