"""Follow each vehicle from frame to frame, so plate votes add up per vehicle.

A simple IoU tracker: a box in the new frame continues the track whose last
box overlaps it most (IoU >= MATCH_IOU). Unmatched boxes start new tracks.
Tracks not seen for max_age_s are returned as lost.
"""

import itertools
from collections import Counter
from concurrent.futures import Future
from dataclasses import dataclass, field

import numpy as np

from app.domain.states import VehicleType
from app.pipeline.detection import Box
from app.pipeline.plate_validator import PlateVoter, VoteResult

MATCH_IOU = 0.3
_ids = itertools.count(1)


@dataclass
class Track:
    box: Box
    voter: PlateVoter
    first_seen: float
    last_seen: float
    track_id: int = field(default_factory=lambda: next(_ids))
    frames: int = 0
    decided: VoteResult | None = None
    type_votes: Counter = field(default_factory=Counter)
    best_conf: float = -1.0
    best_vehicle: np.ndarray | None = None
    best_plate: np.ndarray | None = None
    last_text: str | None = None  # last plate read, for the preview overlay
    ocr_job: Future | None = None  # OCR read running in the OCR thread
    ocr_input: tuple | None = None  # (vehicle image, plate image, frame time)
    ocr_reads: int = 0

    @property
    def vehicle_type(self) -> VehicleType:
        known = {t: n for t, n in self.type_votes.items() if t != VehicleType.UNKNOWN}
        if not known:
            return VehicleType.UNKNOWN
        return Counter(known).most_common(1)[0][0]

    def keep_best(self, conf: float, vehicle: np.ndarray, plate: np.ndarray | None):
        if conf > self.best_conf:
            self.best_conf = conf
            self.best_vehicle = vehicle.copy()
            self.best_plate = None if plate is None else plate.copy()


class Tracker:
    def __init__(self, make_voter=PlateVoter, max_age_s: float = 1.5):
        self.make_voter = make_voter
        self.max_age_s = max_age_s
        self.tracks: list[Track] = []

    def update(self, boxes: list[Box], now: float) -> list[Track]:
        """Return one track per box, in the same order as boxes."""
        pairs = sorted(
            (
                (box.iou(track.box), b, t)
                for b, box in enumerate(boxes)
                for t, track in enumerate(self.tracks)
            ),
            reverse=True,
        )
        matched: dict[int, Track] = {}
        used_tracks: set[int] = set()
        for iou, b, t in pairs:
            if iou < MATCH_IOU:
                break
            if b in matched or t in used_tracks:
                continue
            matched[b] = self.tracks[t]
            used_tracks.add(t)

        result = []
        for b, box in enumerate(boxes):
            track = matched.get(b)
            if track is None:
                track = Track(box, self.make_voter(), first_seen=now, last_seen=now)
                self.tracks.append(track)
            track.box = box
            track.last_seen = now
            track.frames += 1
            result.append(track)
        return result

    def expire(self, now: float) -> list[Track]:
        """Remove and return tracks not seen for max_age_s."""
        lost = [t for t in self.tracks if now - t.last_seen > self.max_age_s]
        self.tracks = [t for t in self.tracks if t not in lost]
        return lost

    def clear(self) -> list[Track]:
        lost, self.tracks = self.tracks, []
        return lost
