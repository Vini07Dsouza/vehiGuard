"""Colour families, the UNKNOWN rule and appearance comparison (Phase 5)."""

import cv2
import numpy as np
import pytest

from app.domain.appearance import Appearance, compare
from app.domain.states import ColourFamily as C
from app.domain.states import VehicleType as V
from app.pipeline.appearance import AppearanceConfig, colour_family

CFG = AppearanceConfig()
RNG = np.random.default_rng(7)


def car(bgr, size=(220, 320), noise=18):
    """A fake vehicle crop: road-grey frame with a body of one colour, with texture."""
    h, w = size
    img = np.full((h, w, 3), 120, np.uint8)
    img[int(h * 0.15) : int(h * 0.85), int(w * 0.1) : int(w * 0.9)] = bgr
    img = img.astype(np.int16) + RNG.integers(-noise, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def hsv_bgr(h, s, v):
    return tuple(int(x) for x in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])  # fmt: skip


COLOURS = [
    ("white", hsv_bgr(0, 10, 230), C.WHITE_SILVER_GREY),
    ("silver", hsv_bgr(0, 8, 170), C.WHITE_SILVER_GREY),
    ("black", hsv_bgr(0, 10, 60), C.BLACK),
    ("red", hsv_bgr(2, 200, 190), C.RED),
    ("red (wrap-around hue)", hsv_bgr(176, 200, 190), C.RED),
    ("blue", hsv_bgr(110, 180, 170), C.BLUE),
    ("green", hsv_bgr(60, 170, 150), C.GREEN),
    ("yellow", hsv_bgr(25, 200, 220), C.YELLOW_ORANGE),
    ("brown", hsv_bgr(15, 160, 100), C.BROWN),
    ("purple", hsv_bgr(150, 150, 150), C.OTHER),
]


@pytest.mark.parametrize(("bgr", "expected"), [c[1:] for c in COLOURS],
                         ids=[c[0] for c in COLOURS])  # fmt: skip
def test_colour_families(bgr, expected):
    reading = colour_family(car(bgr), cfg=CFG)
    assert reading.family == expected and reading.reason == "ok"


def test_plate_pixels_are_left_out_of_the_body_colour():
    img = car(hsv_bgr(110, 180, 170))  # blue car
    h, w = img.shape[:2]
    plate = (int(w * 0.25), int(h * 0.4), int(w * 0.75), int(h * 0.6))
    img[plate[1] : plate[3], plate[0] : plate[2]] = (255, 255, 255)  # white plate
    counted = colour_family(img, None, CFG)
    hidden = colour_family(img, plate, CFG)
    assert counted.family == hidden.family == C.BLUE
    assert hidden.share > counted.share  # the plate no longer dilutes the colour


def test_nothing_left_to_judge_is_unknown():
    img = car(hsv_bgr(110, 180, 170))
    h, w = img.shape[:2]
    plate = (int(w * 0.2), int(h * 0.3), int(w * 0.8), int(h * 0.8))  # covers the body
    assert colour_family(img, plate, CFG).family == C.UNKNOWN


# ---------------------------------------------------------- UNKNOWN rule


@pytest.mark.parametrize(
    ("name", "image", "reason"),
    [
        ("tiny crop", car(hsv_bgr(2, 200, 190), size=(30, 50)), "too_small"),
        ("night: too dark", car(hsv_bgr(2, 200, 12), noise=3), "too_dark"),
        ("overexposed", car((255, 255, 255), noise=2), "overexposed"),
        (
            "blurred",
            cv2.GaussianBlur(car(hsv_bgr(2, 200, 190)), (61, 61), 30),
            "blurred",
        ),
        ("empty", np.zeros((0, 0, 3), np.uint8), "empty"),
    ],
)
def test_unclear_crops_are_unknown(name, image, reason):
    reading = colour_family(image, cfg=CFG)
    assert reading.family == C.UNKNOWN and reading.reason == reason


def test_mixed_colours_are_unknown_not_a_guess():
    img = car(hsv_bgr(2, 200, 190))
    w = img.shape[1]
    img[:, : w // 3] = hsv_bgr(110, 180, 170)  # a third blue
    img[:, w // 3 : 2 * w // 3] = hsv_bgr(60, 170, 150)  # a third green
    reading = colour_family(img, cfg=AppearanceConfig(min_dominant_share=0.6))
    assert reading.family == C.UNKNOWN and reading.reason == "mixed_colours"


# ------------------------------------------------------------- comparison

RED_CAR = Appearance(V.CAR, C.RED)


@pytest.mark.parametrize(
    ("other", "type_mm", "colour_mm"),
    [
        (Appearance(V.CAR, C.RED), False, False),  # same
        (Appearance(V.CAR, C.WHITE_SILVER_GREY), False, True),  # S07: other colour
        (Appearance(V.MOTORCYCLE, C.RED), True, False),  # other type
        (Appearance(V.MOTORCYCLE, C.BLUE), True, True),  # both differ
    ],
)
def test_known_values_that_differ_are_mismatches(other, type_mm, colour_mm):
    diff = compare(RED_CAR, other)
    assert (diff.type_mismatch, diff.colour_mismatch) == (type_mm, colour_mm)
    assert diff.mismatch == (type_mm or colour_mm)


@pytest.mark.parametrize(
    "unclear",
    [
        Appearance(V.UNKNOWN, C.UNKNOWN),
        Appearance(V.CAR, C.UNKNOWN),
        Appearance(V.UNKNOWN, C.BLUE),
        Appearance(V.CAR, C.OTHER),  # catch-all colour is not compared either
    ],
)
def test_unknown_never_causes_a_mismatch(unclear):  # FR-APP-05
    first, second = compare(RED_CAR, unclear), compare(unclear, RED_CAR)
    assert first == second  # order does not matter
    # only the attribute where BOTH are known can differ
    assert not first.colour_mismatch or unclear.colour_family not in (
        C.UNKNOWN,
        C.OTHER,
    )
    assert not first.type_mismatch or unclear.vehicle_type != V.UNKNOWN
    if unclear.vehicle_type == V.CAR:
        assert not first.type_mismatch


def test_two_unknowns_never_mismatch():
    assert not compare(Appearance(V.UNKNOWN, C.UNKNOWN), Appearance(V.UNKNOWN, C.UNKNOWN)).mismatch  # fmt: skip


def test_describe_lists_what_differs():
    other = Appearance(V.MOTORCYCLE, C.BLUE)
    parts = compare(RED_CAR, other).describe(RED_CAR, other)
    assert parts == ["type CAR vs MOTORCYCLE", "colour RED vs BLUE"]


def test_describe_with_only_one_difference():
    other = Appearance(V.CAR, C.BLUE)
    assert compare(RED_CAR, other).describe(RED_CAR, other) == ["colour RED vs BLUE"]
    same_colour = Appearance(V.BUS, C.RED)
    assert compare(RED_CAR, same_colour).describe(RED_CAR, same_colour) == [
        "type CAR vs BUS"
    ]


def test_settings_yaml_provides_the_thresholds():
    cfg = AppearanceConfig.from_settings()
    assert cfg.min_width_px == 60 and cfg.min_dominant_share == 0.40


def test_large_crops_are_shrunk_and_still_read():
    big = car(hsv_bgr(60, 170, 150), size=(900, 1400))
    assert colour_family(big, None, CFG).family == C.GREEN
