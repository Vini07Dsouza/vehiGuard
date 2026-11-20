"""Impossible-journey rule (architecture §8.3), including borderline cases (4.5)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.clone_analyser import (
    CloneConfig,
    SightingPoint,
    analyse,
    check_journey,
)
from app.domain.geo import haversine_km

CFG = CloneConfig(max_speed_kmh=120, min_distance_km=1, tolerance_s=5, window_h=24)
T0 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=UTC)
# Seeded camera positions: A-B about 7 km apart, A-C about 38 km apart
A = (12.9716, 77.5946)
B = (13.0358, 77.5970)
C = (12.7420, 77.3330)
A_NEAR = (12.9750, 77.5946)  # about 0.4 km from A


def at(cam_id, pos, minutes=0.0, seconds=0.0, sid=None):
    when = T0 + timedelta(minutes=minutes, seconds=seconds)
    return SightingPoint(sid or f"{cam_id}@{minutes}m{seconds}s", cam_id, *pos, when)


def test_worked_example_from_architecture():
    """38 km in 6 minutes needs about 380 km/h: impossible."""
    j = check_journey(at("A", A), at("C", C, minutes=6), CFG)
    assert j.distance_km == pytest.approx(38.2, abs=0.2)
    assert j.limit_km == pytest.approx(12.2, abs=0.1)
    assert j.required_speed_kmh == pytest.approx(382, abs=3)
    assert j.impossible


# (name, earlier, later, impossible?)
CASES = [
    ("plausible: 7 km in 10 min (42 km/h)", at("A", A), at("B", B, minutes=10), False),
    ("38 km in 30 min (76 km/h) is possible", at("A", A), at("C", C, minutes=30), False),
    ("38 km in 15 min (153 km/h) is impossible", at("A", A), at("C", C, minutes=15), True),
    ("zero time gap, far apart", at("A", A), at("C", C), True),
    ("zero time gap, cameras too close (< 1 km)", at("A", A), at("N", A_NEAR), False),
    ("cameras too close even at 1 second", at("A", A), at("N", A_NEAR, seconds=1), False),
    ("7 km apart at the same moment is impossible",
     at("A", A), at("B", B), True),
]  # fmt: skip


@pytest.mark.parametrize(
    ("earlier", "later", "impossible"),
    [c[1:] for c in CASES],
    ids=[c[0] for c in CASES],
)
def test_rule(earlier, later, impossible):
    assert check_journey(earlier, later, CFG).impossible is impossible


def test_same_camera_is_never_compared():
    assert check_journey(at("A", A), at("A", A, minutes=1), CFG) is None


def test_zero_gap_has_no_required_speed_but_no_error():
    j = check_journey(at("A", A), at("C", C), CFG)
    assert j.gap_s == 0 and j.required_speed_kmh is None and j.impossible


def boundary_seconds(distance_km):
    """Time gap at which the distance equals the limit exactly."""
    return distance_km / CFG.max_speed_kmh * 3600 - CFG.tolerance_s


@pytest.mark.parametrize(
    ("offset_s", "impossible"),
    [(-1.0, True), (0.0, False), (1.0, False)],
    ids=["1 s faster than the limit", "exactly at the limit", "1 s slower"],
)
def test_exactly_at_the_limit_is_not_flagged(offset_s, impossible):
    d = haversine_km(*A, *C)
    gap = boundary_seconds(d) + offset_s
    j = check_journey(at("A", A), at("C", C, seconds=gap), CFG)
    assert j.impossible is impossible  # rule is d > limit, so equal is allowed


def test_minimum_distance_boundary():
    cfg = CloneConfig(min_distance_km=haversine_km(*A, *A_NEAR))  # exactly d
    j = check_journey(at("A", A), at("N", A_NEAR), cfg)
    assert j.impossible  # d >= min distance counts


# ------------------------------------------------------------------ analyse


def test_analyse_ignores_sightings_outside_the_window():
    new = at("C", C, minutes=25 * 60)
    result = analyse(new, [at("A", A)], CFG)  # 25 h earlier
    assert result.impossible_journey is False and result.checked == ()


def test_analyse_ignores_later_and_same_camera_sightings():
    new = at("C", C, minutes=10)
    earlier = [at("C", C, minutes=5), at("A", A, minutes=20)]  # same cam; later
    result = analyse(new, earlier, CFG)
    assert result.checked == ()


def test_analyse_uses_most_recent_impossible_journey_and_lists_others():
    new = at("C", C, minutes=60)
    old_far = at("A", A, minutes=50, sid="s-old")  # 10 min: impossible
    newest = at("A", A, minutes=55, sid="s-new")  # 5 min: impossible
    plausible = at("B", B, minutes=0, sid="s-b")  # B-C is 39.5 km in 60 min
    result = analyse(new, [old_far, plausible, newest], CFG)
    assert result.impossible_journey
    assert result.journey.from_sighting == "s-new"
    data = result.journey_json()
    assert [j["from_sighting"] for j in data["other_impossible"]] == ["s-old"]
    assert len(result.checked) == 3


def test_analyse_without_earlier_sightings():
    result = analyse(at("A", A), [], CFG)
    assert (result.impossible_journey, result.journey, result.journey_json()) == (
        False,
        None,
        None,
    )


def test_config_from_settings():
    cfg = CloneConfig.from_settings(
        {
            "max_plausible_speed_kmh": 100,
            "min_clone_distance_km": 2,
            "time_tolerance_s": 10,
            "clone_window_h": 12,
        }
    )
    assert cfg == CloneConfig(100, 2, 10, 12)
