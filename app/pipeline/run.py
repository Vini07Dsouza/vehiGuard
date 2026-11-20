"""Run the plate pipeline on one or more cameras (Phase 2).

Examples (from the project folder):
    python -m app.pipeline.run --camera CAM-A                 # source from database
    python -m app.pipeline.run --camera CAM-A --source http://192.168.1.2:8080
    python -m app.pipeline.run --camera CAM-B --source data/test_plates --no-db
    python -m app.pipeline.run --camera CAM-A --camera CAM-B  # two cameras
    python -m app.pipeline.run --camera CAM-A=data/a --camera CAM-C=data/c  # replay pair

Per frame: detect vehicles and plates, read each plate (OCR), validate,
and vote per vehicle. A finished vehicle becomes a sighting with evidence.
Press q in the preview window to stop.
"""

import argparse
import logging
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass, field

import cv2

from app.core.config import load_yaml
from app.domain.states import CameraStatus, VehicleType
from app.pipeline.appearance import colour_family
from app.pipeline.capture import Frame, FrameGrabber
from app.pipeline.detection import Box, Detection
from app.pipeline.ocr import PlateReader
from app.pipeline.plate_detector import PlateDetector
from app.pipeline.plate_validator import VoteResult, VoteStatus
from app.pipeline.tracker import Track, Tracker
from app.pipeline.vehicle_detector import VehicleDetector
from app.services.sightings import PlateEvent

log = logging.getLogger("vehiguard.pipeline")
MIN_FRAMES_FOR_EVENT = 3  # ignore vehicles seen for fewer frames (noise)
HEALTH_EVERY_S = 5.0


@dataclass
class Models:
    """Loaded once and shared by all cameras; each model has its own lock."""

    vehicles: VehicleDetector
    plates: PlateDetector
    reader: PlateReader
    vehicle_lock: threading.Lock = field(default_factory=threading.Lock)
    plate_lock: threading.Lock = field(default_factory=threading.Lock)
    # One OCR thread for all cameras: reads run beside detection, one at a time
    ocr_pool: ThreadPoolExecutor = field(
        default_factory=lambda: ThreadPoolExecutor(1, thread_name_prefix="ocr")
    )

    @classmethod
    def load(cls) -> "Models":
        log.info("Loading models (first time can take a minute)...")
        import torch

        # Split the CPU between YOLO (PyTorch) and PaddleOCR so they do not
        # fight over the same cores (that made detection 4x slower).
        perf = load_yaml("settings.yaml").get("performance", {})
        torch.set_num_threads(int(perf.get("detector_threads", 4)))
        models = cls(VehicleDetector(), PlateDetector(), PlateReader())
        for name in models.reader.engine_names:
            models.reader.engine(name)
        return models


def pair_plates_with_vehicles(
    vehicles: list[Detection], plates: list[Detection]
) -> list[tuple[Box, VehicleType, Detection | None]]:
    """Give each plate to the smallest vehicle box that contains its centre.

    Plates outside every vehicle box (e.g. close-up photos) become their own
    entry with an UNKNOWN vehicle type.
    """
    entries = [[v.box, v.label, None] for v in vehicles]
    for plate in sorted(plates, key=lambda p: -p.conf):
        cx, cy = plate.box.centre
        inside = [e for e in entries if e[0].contains_point(cx, cy) and e[2] is None]
        if inside:
            min(inside, key=lambda e: e[0].area)[2] = plate
        else:
            entries.append([plate.box, VehicleType.UNKNOWN, plate])
    return [tuple(e) for e in entries]


class CameraWorker:
    def __init__(self, camera_id, source, models, on_event, fps=None, db=True,
                 loop=False, sync=None):  # fmt: skip
        self.camera_id = camera_id
        self.models = models
        self.on_event = on_event
        self.db = db
        settings = load_yaml("settings.yaml")
        self.fps = fps or settings["pipeline"]["frame_fps"]
        self.thorough_every = max(1, settings["ocr"].get("thorough_every", 4))
        self.vehicle_every = max(1, settings["detection"].get("vehicle_every", 2))
        self.grabber = FrameGrabber(camera_id, source, loop=loop, sync=sync)
        self.tracker = Tracker()
        self.preview = None
        self.frames = 0
        self.busy_s = 0.0
        self.stage_totals: Counter = Counter()
        self.events: Counter = Counter()
        self._scene = None
        self._new_scene = True
        self._vehicles: list[Detection] = []
        self._stop = threading.Event()
        self._thread = None
        self._last_health = 0.0

    # ----------------------------------------------------------- lifecycle
    def start(self):
        self.grabber.start()
        self.started_at = time.time()
        self._thread = threading.Thread(target=self._run, name=f"cam-{self.camera_id}", daemon=True)  # fmt: skip
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        self.grabber.stop()
        self._update_health(force=True)

    @property
    def done(self) -> bool:
        return self._thread is not None and not self._thread.is_alive()

    def _run(self):
        seq, gap = 0, 1 / self.fps
        try:
            while not self._stop.is_set():
                frame = self.grabber.latest(after_seq=seq, wait_s=1.0)
                if frame is None:
                    if self.grabber.finished:
                        break
                    self._update_health()
                    continue
                seq = frame.seq
                started = time.perf_counter()
                self.process(frame)
                spent = time.perf_counter() - started
                self.busy_s += spent
                self._update_health()
                if not self.grabber.sync:  # live: do not exceed the frame rate
                    self._stop.wait(max(0.0, gap - spent))
        except Exception:
            log.exception("%s: pipeline stopped by an error", self.camera_id)
        finally:
            for track in self.tracker.clear():
                self._finish_track(track, time.time())

    # ---------------------------------------------------------- per frame
    def process(self, frame: Frame) -> None:
        t0 = time.perf_counter()
        stages = {"capture_lag": (time.time() - frame.ts) * 1000}
        if frame.scene != self._scene:  # new image in folder replay
            for track in self.tracker.clear():
                self._finish_track(track, frame.ts)
            self._scene = frame.scene
            self._new_scene = True

        img = frame.image
        # Vehicles move little between frames: detect them every Nth frame
        # (always on a new replay image) and reuse the boxes in between.
        if self.frames % self.vehicle_every == 0 or self._new_scene:
            with self.models.vehicle_lock:
                t = time.perf_counter()
                self._vehicles = self.models.vehicles.detect(img)
                stages["vehicle_detect"] = (time.perf_counter() - t) * 1000
            self._new_scene = False
        vehicles = self._vehicles
        with self.models.plate_lock:
            t = time.perf_counter()
            plates = self.models.plates.detect(img)
            stages["plate_detect"] = (time.perf_counter() - t) * 1000

        entries = pair_plates_with_vehicles(vehicles, plates)
        tracks = self.tracker.update([e[0] for e in entries], frame.ts)
        for track, (box, vtype, plate) in zip(tracks, entries, strict=True):
            track.type_votes[vtype] += 1
            if track.decided:
                continue
            if vtype != VehicleType.UNKNOWN:  # a real vehicle box, not a lone plate
                track.colour_votes[self._read_colour(img, box, plate)] += 1
            vote = self._collect_ocr(track, stages)
            if vote.status == VoteStatus.WAITING:
                if plate is None:
                    # no plate visible in this frame: a reading of "nothing"
                    track.keep_best(0.0, box.crop(img), None)
                    vote = track.voter.add(None, 0.0, frame.ts)
                elif track.ocr_job is None:
                    self._start_ocr(track, box.crop(img), plate.box.crop(img), frame.ts)
                    if self.grabber.sync:  # replay: wait, so results repeat exactly
                        track.ocr_job.result()
                        vote = self._collect_ocr(track, stages)
                    else:
                        vote = track.voter.check_timeout(frame.ts)
                else:
                    vote = track.voter.check_timeout(frame.ts)
            if vote.status != VoteStatus.WAITING:
                track.decided = vote
                stages["time_to_decide"] = (frame.ts - track.first_seen) * 1000
                self._emit(track, vote, frame.ts, stages)

        for track in self.tracker.expire(frame.ts):
            self._finish_track(track, frame.ts)

        stages["total"] = (time.perf_counter() - t0) * 1000
        self.frames += 1
        self.stage_totals.update(stages)
        self.preview = self._draw(img, tracks, entries)

    @staticmethod
    def _read_colour(img, box: Box, plate: Detection | None):
        """Colour family of one vehicle box, hiding the plate area."""
        plate_in_crop = None
        if plate is not None:
            p = plate.box
            plate_in_crop = (p.x1 - box.x1, p.y1 - box.y1, p.x2 - box.x1, p.y2 - box.y1)
        return colour_family(box.crop(img), plate_in_crop).family

    # ------------------------------------------------------------------ OCR
    def _start_ocr(self, track: Track, vehicle_img, plate_img, ts: float) -> None:
        """Read the plate in the OCR thread, so detection keeps its frame rate.

        Every Nth read of a vehicle also tries the slower fallback engines.
        """
        thorough = track.ocr_reads % self.thorough_every == self.thorough_every - 1
        track.ocr_reads += 1
        reader = self.models.reader

        def job():
            t = time.perf_counter()
            result = reader.read(plate_img, thorough=thorough)
            return result, (time.perf_counter() - t) * 1000

        track.ocr_job = self.models.ocr_pool.submit(job)
        track.ocr_input = (vehicle_img, plate_img, ts)

    def _collect_ocr(self, track: Track, stages: dict) -> VoteResult:
        """Add a finished OCR read to the vehicle's votes."""
        job = track.ocr_job
        if job is None or not job.done():
            return VoteResult(VoteStatus.WAITING)
        track.ocr_job = None
        vehicle_img, plate_img, ts = track.ocr_input
        try:
            result, ms = job.result()
        except Exception:
            log.exception("%s: OCR failed", self.camera_id)
            return VoteResult(VoteStatus.WAITING)
        stages["ocr"] = stages.get("ocr", 0.0) + ms
        text, conf = result.plate, result.confidence
        track.last_text = text or result.raw or None
        track.keep_best(conf if text else 0.0, vehicle_img, plate_img)
        return track.voter.add(text, conf, ts)

    def _finish_track(self, track: Track, now: float) -> None:
        if track.decided or track.frames < MIN_FRAMES_FOR_EVENT:
            return
        vote = track.voter.close()
        self._emit(track, vote, now, {"time_to_decide": (now - track.first_seen) * 1000})  # fmt: skip

    def _emit(self, track: Track, vote: VoteResult, ts: float, stages: dict):
        self.events[vote.status] += 1
        event = PlateEvent(
            camera_id=self.camera_id,
            status=vote.status,
            observed_at=ts,
            plate=vote.plate,
            confidence=vote.confidence,
            vehicle_type=track.vehicle_type,
            colour_family=track.colour_family,
            vehicle_image=track.best_vehicle,
            plate_image=track.best_plate,
            stage_ms={k: round(v, 1) for k, v in stages.items()},
        )
        try:
            self.on_event(event)
        except Exception:
            log.exception("%s: could not record event", self.camera_id)

    # ------------------------------------------------------------- display
    def _draw(self, img, tracks, entries):
        view = img.copy()
        for track, (box, vtype, plate) in zip(tracks, entries, strict=True):
            cv2.rectangle(view, (box.x1, box.y1), (box.x2, box.y2), (0, 200, 0), 2)
            if plate is not None:
                p = plate.box
                cv2.rectangle(view, (p.x1, p.y1), (p.x2, p.y2), (0, 220, 255), 2)
            if track.decided and track.decided.plate:
                label, colour = f"{track.decided.plate} OK", (0, 255, 0)
            elif track.decided:
                label, colour = track.decided.status.value, (0, 0, 255)
            else:
                label, colour = f"{track.last_text or '...'}", (0, 220, 255)
            cv2.putText(view, f"{track.vehicle_type.value} {label}",
                        (box.x1, max(box.y1 - 8, 20)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, colour, 2)  # fmt: skip
        fps = self.frames / max(self.busy_s, 1e-6)
        cv2.putText(view, f"{self.camera_id}  {fps:.1f} fps", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)  # fmt: skip
        return view

    def _update_health(self, force=False):
        """Write camera status and last frame time to the database (FR-CAP-07)."""
        now = time.time()
        if not self.db or (not force and now - self._last_health < HEALTH_EVERY_S):
            return
        self._last_health = now
        from datetime import UTC, datetime

        from app.db.models import Camera
        from app.db.session import SessionLocal

        status = CameraStatus.STOPPED if self._stop.is_set() else self.grabber.status
        last = self.grabber.last_frame_at
        try:
            with SessionLocal() as session:
                camera = session.get(Camera, self.camera_id)
                if camera:
                    camera.status = status
                    if last:
                        camera.last_frame_at = datetime.fromtimestamp(last, UTC)
                    session.commit()
        except Exception:
            log.exception("%s: could not update camera health", self.camera_id)

    def summary(self) -> str:
        n = max(self.frames, 1)
        avg = {k: round(v / n) for k, v in self.stage_totals.items() if k != "time_to_decide"}  # fmt: skip
        return (
            f"{self.camera_id}: {self.frames} frames, "
            f"{self.frames / max(self.busy_s, 1e-6):.1f} fps processing, "
            f"reconnects {self.grabber.reconnects}, events {dict(self.events)}, "
            f"avg ms {avg}"
        )


def database_recorder():
    from app.db.session import SessionLocal
    from app.services.sightings import record_sighting

    lock = threading.Lock()

    def record(event: PlateEvent) -> None:
        with lock, SessionLocal() as session:
            result = record_sighting(session, event)
            session.commit()
            alerts = ", ".join(
                f"{a.alert_type}/{a.severity}"
                + (f" (merged x{a.merged_count})" if a.merged_count > 1 else "")
                for a in result.alerts
            )
            if result.duplicate:
                log.info("%s %s %s -> same visit as earlier sighting (merged)",
                         event.camera_id, event.status, event.plate)  # fmt: skip
                return
            journey = ""
            if result.clone and result.clone.journey:
                j = result.clone.journey
                journey = (f" | journey {j.from_camera}->{j.to_camera} "
                           f"{j.distance_km:.1f} km in {j.gap_s:.0f} s")  # fmt: skip
            log.info("%s %s %s -> %s %s%s", event.camera_id, event.status,
                     event.plate or "-", result.sighting.outcome,
                     f"ALERT {alerts}" if alerts else "", journey)  # fmt: skip

    return record


def print_recorder(event: PlateEvent) -> None:
    log.info("%s %s %s conf=%s type=%s", event.camera_id, event.status,
             event.plate or "-", event.confidence, event.vehicle_type)  # fmt: skip


def camera_sources(camera_ids: list[str]) -> dict[str, str]:
    from app.db.models import Camera
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        sources = {}
        for cid in camera_ids:
            camera = session.get(Camera, cid)
            if camera is None or not camera.source_url:
                raise SystemExit(
                    f"Camera {cid} is not in the database or has no source"
                )
            sources[cid] = camera.source_url
        return sources


def parse_cameras(cameras: list[str], source: str | None, no_db: bool) -> dict:
    """--camera ID (source from the database) or --camera ID=SOURCE.

    --source sets the source of a single --camera ID.
    """
    if source:
        if len(cameras) != 1 or "=" in cameras[0]:
            raise SystemExit("--source works with exactly one --camera ID")
        return {cameras[0]: source}
    given = dict(c.split("=", 1) for c in cameras if "=" in c)
    missing = [c for c in cameras if "=" not in c]
    if missing and no_db:
        raise SystemExit("--no-db needs a source: --camera ID=SOURCE or --source")
    sources = camera_sources(missing) if missing else {}
    return {**sources, **given}


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)  # fmt: skip
    parser.add_argument("--camera", action="append", required=True, help="camera id, or ID=SOURCE (repeat for more)")  # fmt: skip
    parser.add_argument("--source", help="override the source (only with one --camera)")  # fmt: skip
    parser.add_argument("--no-db", action="store_true", help="print results, do not store")  # fmt: skip
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--seconds", type=float, default=0, help="stop after N seconds")  # fmt: skip
    parser.add_argument("--fps", type=float, help="processing rate per camera")
    parser.add_argument("--loop", action="store_true", help="repeat a replay source")  # fmt: skip
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")  # fmt: skip
    for noisy in ("ppocr", "paddlex", "paddle", "ultralytics", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    sources = parse_cameras(args.camera, args.source, args.no_db)

    models = Models.load()
    on_event = print_recorder if args.no_db else database_recorder()
    outbox = None
    if not args.no_db:  # deliver alert emails in the background (outbox)
        from app.services.outbox import start_scheduler

        outbox = start_scheduler()
    workers = []
    for cid, src in sources.items():
        worker = CameraWorker(
            cid, src, models, on_event, fps=args.fps, db=not args.no_db, loop=args.loop
        )
        workers.append(worker.start())
    log.info("Running %s. Press q in a preview window (or Ctrl+C) to stop.",
             ", ".join(f"{w.camera_id} <- {w.grabber.source}" for w in workers))  # fmt: skip
    started = time.time()
    try:
        while not all(w.done for w in workers):
            if args.seconds and time.time() - started >= args.seconds:
                break
            if args.no_preview:
                time.sleep(0.2)
                continue
            for w in workers:
                if w.preview is not None:
                    cv2.imshow(f"VehiGuard {w.camera_id} (q = quit)", w.preview)
            if cv2.waitKey(30) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        with nullcontext():
            for w in workers:
                w.stop()
            cv2.destroyAllWindows()
        if outbox:  # one last delivery round for alerts raised at the end
            from app.db.session import SessionLocal
            from app.services.outbox import dispatch_due

            outbox.shutdown(wait=False)
            with SessionLocal() as session:
                dispatch_due(session)
                session.commit()
        for w in workers:
            log.info(w.summary())


if __name__ == "__main__":
    main()
