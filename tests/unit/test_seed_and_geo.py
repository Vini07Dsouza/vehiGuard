"""Checks on the seed data, distances and hashing (no database needed)."""

import re

import pytest

from app.core.config import load_yaml
from app.core.security import hash_password, verify_password
from app.domain.geo import haversine_km
from scripts import seed_data as seed

PATTERNS = load_yaml("plate_patterns.yaml")
STANDARD = re.compile(PATTERNS["patterns"]["standard"])
BH = re.compile(PATTERNS["patterns"]["bh_series"])


def is_valid_plate(plate):
    if BH.match(plate):
        return True
    return bool(STANDARD.match(plate)) and plate[:2] in PATTERNS["state_codes"]


def cam(camera_id):
    c = next(c for c in seed.CAMERAS if c[0] == camera_id)
    return c[3], c[4]


def test_haversine_zero_and_known_distance():
    assert haversine_km(12.97, 77.59, 12.97, 77.59) == 0
    # one degree of latitude is about 111 km
    assert haversine_km(12.0, 77.0, 13.0, 77.0) == pytest.approx(111.2, abs=0.2)


def test_clone_test_cameras_are_about_38_km_apart():
    assert haversine_km(*cam("CAM-A"), *cam("CAM-C")) == pytest.approx(38, abs=1)


def test_plausible_journey_cameras_are_close():
    assert haversine_km(*cam("CAM-A"), *cam("CAM-B")) < 10


def test_seed_has_planned_amounts():
    assert 20 <= len(seed.VEHICLES) <= 30
    assert 4 <= len(seed.REPORTS) <= 6
    assert len(seed.STATIONS) == 3 and len(seed.CAMERAS) == 3


def test_every_seed_plate_is_a_valid_indian_plate():
    plates = [v[0] for v in seed.VEHICLES] + list(seed.UNREGISTERED_TEST_PLATES)
    assert [p for p in plates if not is_valid_plate(p)] == []


def test_reports_point_at_registered_vehicles():
    registered = {v[0] for v in seed.VEHICLES}
    assert {r[0] for r in seed.REPORTS} <= registered
    assert not registered & set(seed.UNREGISTERED_TEST_PLATES)


def test_reports_cover_every_recovery_status_and_type():
    assert {r[5] for r in seed.REPORTS} == set(seed.STATUS_PATH)
    assert {r[1] for r in seed.REPORTS} == {"STOLEN", "MISSING"}


def test_password_hashing():
    h = hash_password("s3cret-pass")
    assert h.startswith("$2") and verify_password("s3cret-pass", h)
    assert not verify_password("wrong", h)
    with pytest.raises(ValueError):
        hash_password("x" * 73)
