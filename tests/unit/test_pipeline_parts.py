"""Pipeline building blocks that need no models or database."""

import cv2
import numpy as np
import pytest

from app.domain.states import VehicleType
from app.pipeline import preprocess
from app.pipeline.capture import FrameGrabber, source_kind, stream_url
from app.pipeline.detection import Box, Detection
from app.pipeline.ocr import Segment, order_segments
from app.pipeline.plate_validator import PlateVoter, VoteStatus
from app.pipeline.run import pair_plates_with_vehicles
from app.pipeline.tracker import Tracker

# ------------------------------------------------------------------ boxes


def test_iou_of_same_and_separate_boxes():
    a = Box(0, 0, 10, 10)
    assert a.iou(a) == 1
    assert a.iou(Box(20, 20, 30, 30)) == 0
    assert a.iou(Box(5, 0, 15, 10)) == pytest.approx(50 / 150)


def test_padding_is_clipped_to_the_image():
    padded = Box(0, 0, 100, 20).padded(0.1, 0.5, width=105, height=200)
    assert padded == Box(0, 0, 105, 30)


# ------------------------------------------------------- plate to vehicle


def det(x1, y1, x2, y2, label="CAR", conf=0.9):
    return Detection(Box(x1, y1, x2, y2), conf, label)


def test_plate_goes_to_the_vehicle_that_contains_it():
    car, bike = det(0, 0, 200, 200), det(300, 0, 400, 200, "MOTORCYCLE")
    plate = det(320, 150, 380, 170, "PLATE")
    entries = pair_plates_with_vehicles([car, bike], [plate])
    assert entries[0][2] is None
    assert entries[1][1] == "MOTORCYCLE" and entries[1][2] == plate


def test_nested_boxes_choose_the_smallest_vehicle():
    bus, car = det(0, 0, 500, 500, "BUS"), det(100, 100, 200, 200)
    plate = det(140, 180, 160, 190, "PLATE")
    entries = pair_plates_with_vehicles([bus, car], [plate])
    assert entries[1][2] == plate and entries[0][2] is None


def test_plate_without_vehicle_becomes_its_own_entry():
    entries = pair_plates_with_vehicles([], [det(10, 10, 110, 40, "PLATE")])
    assert entries[0][1] == VehicleType.UNKNOWN


# ---------------------------------------------------------------- tracker


def test_tracker_keeps_identity_while_box_moves():
    tracker = Tracker(make_voter=lambda: PlateVoter(10, 0.7, 10))
    first = tracker.update([Box(0, 0, 100, 100)], now=0.0)[0]
    second = tracker.update([Box(10, 0, 110, 100)], now=0.2)[0]
    assert first is second and second.frames == 2


def test_tracker_starts_new_track_for_far_box_and_expires_old():
    tracker = Tracker(make_voter=lambda: PlateVoter(10, 0.7, 10), max_age_s=1.0)
    a = tracker.update([Box(0, 0, 100, 100)], now=0.0)[0]
    b = tracker.update([Box(500, 500, 600, 600)], now=0.5)[0]
    assert a is not b
    assert tracker.expire(now=1.2) == [a]
    assert tracker.tracks == [b]


def test_voter_close_reports_no_plate_or_low_confidence():
    voter = PlateVoter(10, 0.7, 10)
    voter.add(None, 0.0, 0.0)
    assert voter.close().status == VoteStatus.NO_PLATE
    for i in range(6):
        voter.add("KA19AB1234", 0.3, i * 0.1)
    assert voter.close().status == VoteStatus.LOW_CONFIDENCE


# -------------------------------------------------------------------- OCR


def test_two_line_plate_is_read_top_row_first():
    bottom = Segment("AB1234", 0.9, [[0, 50], [100, 50], [100, 80], [0, 80]])
    top_right = Segment("19", 0.9, [[60, 0], [100, 0], [100, 30], [60, 30]])
    top_left = Segment("KA", 0.9, [[0, 2], [50, 2], [50, 32], [0, 32]])
    ordered = order_segments([bottom, top_right, top_left])
    assert "".join(s.text for s in ordered) == "KA19AB1234"


# --------------------------------------------------------------- preprocess


def test_small_crops_are_upscaled_and_large_ones_kept():
    small = np.zeros((40, 150, 3), np.uint8)
    assert preprocess.preprocess(small).shape[1] == preprocess.TARGET_WIDTH
    big = np.zeros((200, 800), np.uint8)
    assert preprocess.upscale(big).shape == (200, 800)


def test_deskew_finds_the_tilt_of_text_lines():
    img = np.full((200, 600), 255, np.uint8)
    for y in (60, 100, 140):
        cv2.line(img, (50, y), (550, y), 0, 4)
    rotation = cv2.getRotationMatrix2D((300, 100), 7, 1.0)
    tilted = cv2.warpAffine(img, rotation, (600, 200), borderValue=255)
    assert abs(preprocess.estimate_skew(tilted)) == pytest.approx(7, abs=1.5)
    assert abs(preprocess.estimate_skew(preprocess.deskew(tilted))) < 1.5


def test_variants_have_expected_names():
    assert set(preprocess.variants(np.zeros((50, 200, 3), np.uint8))) == {
        "gray",
        "full",
        "binary",
    }


# ----------------------------------------------------------------- capture


def test_phone_addresses_get_video_path():
    assert stream_url("http://192.168.1.2:8080") == "http://192.168.1.2:8080/video"
    assert (
        stream_url("http://192.168.1.2:8080/video") == "http://192.168.1.2:8080/video"
    )
    assert stream_url("http://x:4747/") == "http://x:4747/video"


def test_source_kinds(tmp_path):
    assert source_kind("0") == "webcam"
    assert source_kind("rtsp://cam/stream") == "stream"
    assert source_kind(str(tmp_path)) == "folder"
    assert source_kind("data/test_sessions/cam_b.mp4") == "video"


def test_folder_replay_hands_over_every_frame_in_order(tmp_path):
    for name in ("a.jpg", "b.jpg"):
        cv2.imwrite(str(tmp_path / name), np.zeros((20, 20, 3), np.uint8))
    grabber = FrameGrabber("T", str(tmp_path), image_repeat=3).start()
    scenes, seq = [], 0
    while (frame := grabber.latest(after_seq=seq, wait_s=2)) is not None:
        seq = frame.seq
        scenes.append(frame.scene)
    grabber.stop()
    assert scenes == [1, 1, 1, 2, 2, 2]


def test_two_line_plates_use_full_paddleocr_first():
    from app.pipeline.ocr import PlateReader

    reader = PlateReader(engines=["paddle_rec", "paddleocr", "easyocr"])
    wide = np.zeros((100, 500, 3), np.uint8)  # one-line plate
    tall = np.zeros((200, 300, 3), np.uint8)  # two-line plate
    assert reader.engines_for(wide) == ["paddle_rec", "paddleocr", "easyocr"]
    assert reader.engines_for(tall) == ["paddleocr", "paddle_rec", "easyocr"]
