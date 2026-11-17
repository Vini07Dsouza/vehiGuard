"""Find vehicles with a pre-trained YOLOv8 model (FR-PLT-01, task 2.2)."""

from ultralytics import YOLO

from app.core.config import ROOT_DIR, load_yaml
from app.domain.states import VehicleType
from app.pipeline.detection import Box, Detection

# COCO class ids used by the pre-trained YOLO models
COCO_VEHICLES = {
    2: VehicleType.CAR,
    3: VehicleType.MOTORCYCLE,
    5: VehicleType.BUS,
    7: VehicleType.TRUCK,
}


class VehicleDetector:
    def __init__(self, weights: str | None = None, conf: float | None = None):
        cfg = load_yaml("settings.yaml")["detection"]
        self.model = YOLO(str(ROOT_DIR / (weights or cfg["vehicle_model"])))
        self.conf = conf if conf is not None else cfg["vehicle_conf"]
        self.imgsz = cfg["vehicle_imgsz"]

    def detect(self, frame) -> list[Detection]:
        result = self.model(
            frame,
            conf=self.conf,
            imgsz=self.imgsz,
            classes=list(COCO_VEHICLES),
            verbose=False,
        )[0]
        found = []
        for xyxy, conf, cls in zip(
            result.boxes.xyxy.tolist(),
            result.boxes.conf.tolist(),
            result.boxes.cls.tolist(),
            strict=True,
        ):
            box = Box(*(int(v) for v in xyxy))
            found.append(Detection(box, float(conf), COCO_VEHICLES[int(cls)]))
        return found
