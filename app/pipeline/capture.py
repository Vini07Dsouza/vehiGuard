"""One frame grabber per camera (FR-CAP-01/02/04/06, task 2.1).

Sources (FR-CAP-02, replay mode):
  - phone stream:  "http://192.168.1.2:8080"  (IP Webcam / DroidCam; /video added)
  - webcam:        "0"
  - video file:    "data/test_sessions/cam_b.mp4"  (played at its own speed)
  - image folder:  "data/test_plates"  (each image shown for a few frames)

The grabber runs in its own thread and keeps only the newest frame, so the
pipeline never falls behind a live stream. Every frame gets a server
timestamp when it arrives (ADR-08). A dropped stream is reopened
automatically (FR-CAP-06).
"""

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.core.config import ROOT_DIR
from app.domain.states import CameraStatus

log = logging.getLogger(__name__)

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp"}
STREAM_PATHS = {"8080": "/video", "4747": "/video"}  # IP Webcam, DroidCam
TIMEOUT_MS = 5000  # give up on a silent stream after 5 s, then reconnect
RECONNECT_DELAYS_S = (1, 2, 3)  # wait between reconnect attempts (then 3 s)


@dataclass(frozen=True)
class Frame:
    image: np.ndarray
    ts: float  # server clock, seconds since epoch
    seq: int  # increases by one for every frame received
    scene: int = 0  # image number in folder replay (a new scene = new vehicles)


def stream_url(url: str) -> str:
    """Add /video to a phone camera address if it is missing."""
    base = url.rstrip("/")
    port = base.rsplit(":", 1)[-1]
    if port in STREAM_PATHS and not base.endswith("/video"):
        return base + STREAM_PATHS[port]
    return base


def source_kind(source: str) -> str:
    if source.isdigit():
        return "webcam"
    if source.startswith(("http://", "https://", "rtsp://")):
        return "stream"
    path = ROOT_DIR / source if not Path(source).is_absolute() else Path(source)
    return "folder" if path.is_dir() else "video"


class FrameGrabber:
    def __init__(self, camera_id: str, source: str, image_repeat: int = 12,
                 folder_fps: float = 5.0, loop: bool = False,
                 sync: bool | None = None):  # fmt: skip
        self.camera_id = camera_id
        self.source = source
        self.kind = source_kind(source)
        # sync: hand over every frame and wait until it is taken (no drops).
        # Default on for image folders, so replays are repeatable.
        self.sync = self.kind == "folder" if sync is None else sync
        self._taken_seq = 0
        self.image_repeat = image_repeat  # frames per image (voting needs 6+)
        self.folder_fps = folder_fps
        self.loop = loop
        self.status = CameraStatus.STOPPED
        self.last_frame_at: float | None = None
        self.reconnects = 0
        self.finished = False  # replay source has no more frames
        self._latest: Frame | None = None
        self._seq = 0
        self._lock = threading.Lock()
        self._new_frame = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------- public
    def start(self) -> "FrameGrabber":
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"grab-{self.camera_id}", daemon=True
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        with self._new_frame:
            self._new_frame.notify_all()
        if self._thread:
            self._thread.join(timeout=TIMEOUT_MS / 1000 + 2)
        self.status = CameraStatus.STOPPED

    def latest(self, after_seq: int = 0, wait_s: float = 1.0) -> Frame | None:
        """Newest frame newer than after_seq; waits up to wait_s for one."""
        deadline = time.monotonic() + wait_s
        with self._new_frame:
            while not self._stop.is_set():
                if self._latest and self._latest.seq > after_seq:
                    self._taken_seq = self._latest.seq
                    self._new_frame.notify_all()  # wakes a waiting sync producer
                    return self._latest
                if self.finished:
                    return None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._new_frame.wait(remaining)
        return None

    # ------------------------------------------------------------ internals
    def _publish(self, image: np.ndarray, scene: int = 0) -> None:
        with self._new_frame:
            while self.sync and self._taken_seq < self._seq and not self._stop.is_set():
                self._new_frame.wait(0.5)  # wait until the last frame was taken
            self._seq += 1
            now = time.time()
            self._latest = Frame(image, now, self._seq, scene)
            self.last_frame_at = now
            self.status = CameraStatus.ONLINE
            self._new_frame.notify_all()

    def _run(self) -> None:
        try:
            if self.kind == "folder":
                self._run_folder()
            else:
                self._run_capture()
        finally:
            with self._new_frame:
                self.finished = True
                self._new_frame.notify_all()

    def _open(self) -> cv2.VideoCapture:
        if self.kind == "webcam":
            return cv2.VideoCapture(int(self.source))
        target = stream_url(self.source) if self.kind == "stream" else self.source
        if self.kind == "video" and not Path(target).is_absolute():
            target = str(ROOT_DIR / target)
        cap = cv2.VideoCapture(
            target,
            cv2.CAP_FFMPEG,
            [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, TIMEOUT_MS,
             cv2.CAP_PROP_READ_TIMEOUT_MSEC, TIMEOUT_MS],
        )  # fmt: skip
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def _run_capture(self) -> None:
        live = self.kind in ("stream", "webcam")
        attempt = 0
        while not self._stop.is_set():
            cap = self._open()
            if not cap.isOpened():
                cap.release()
                if not live:
                    log.error("%s: cannot open %s", self.camera_id, self.source)
                    return
                self._wait_before_reconnect(attempt)
                attempt += 1
                continue
            attempt = 0
            frame_gap = 1 / (cap.get(cv2.CAP_PROP_FPS) or 25) if not live else 0
            next_due = time.monotonic()
            while not self._stop.is_set():
                ok, image = cap.read()
                if not ok:
                    break
                self._publish(image)
                if frame_gap:  # play files at their real speed
                    next_due += frame_gap
                    time.sleep(max(0.0, next_due - time.monotonic()))
            cap.release()
            if self._stop.is_set():
                return
            if not live:
                if self.loop:
                    continue
                return
            log.warning("%s: stream dropped, reconnecting", self.camera_id)
            self.status = CameraStatus.OFFLINE
            self.reconnects += 1
            self._wait_before_reconnect(attempt)
            attempt += 1

    def _wait_before_reconnect(self, attempt: int) -> None:
        self.status = CameraStatus.OFFLINE
        delay = RECONNECT_DELAYS_S[min(attempt, len(RECONNECT_DELAYS_S) - 1)]
        self._stop.wait(delay)

    def _run_folder(self) -> None:
        folder = Path(self.source)
        folder = folder if folder.is_absolute() else ROOT_DIR / folder
        images = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_TYPES)
        gap = 1 / self.folder_fps
        while not self._stop.is_set():
            for scene, path in enumerate(images, 1):
                image = cv2.imread(str(path))
                if image is None:
                    continue
                for _ in range(self.image_repeat):
                    if self._stop.is_set():
                        return
                    self._publish(image, scene)
                    if not self.sync:
                        self._stop.wait(gap)
            if not self.loop:
                return
