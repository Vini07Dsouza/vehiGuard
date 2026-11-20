"""Near-miss plate matching (FR-PLT-08) and nearest station (FR-GEO-02)."""

from types import SimpleNamespace

import pytest

from app.domain.fuzzy import edit_distance, near_misses
from app.domain.geo import nearest


@pytest.mark.parametrize(
    ("a", "b", "distance"),
    [
        ("KA21GH1357", "KA21GH1357", 0),
        ("KA21GH1357", "KA21GH1358", 1),  # one character replaced
        ("KA21GH1357", "KA21G1357", 1),  # one character missing
        ("KA21GH1357", "KA21GHH1357", 1),  # one character extra
        ("KA21GH1357", "KA21GH1388", 2),
        ("", "AB", 2),
    ],
)
def test_edit_distance(a, b, distance):
    assert edit_distance(a, b) == distance


def test_edit_distance_stops_early_above_limit():
    assert edit_distance("KA21GH1357", "TN09ZZ0000", limit=1) == 2
    assert edit_distance("AB", "ABCDE", limit=1) == 2


def test_near_misses_exclude_exact_and_far_plates():
    stolen = ["KA21GH1357", "KA21GH1357", "KA51AC3344", "KA21GH1358"]
    assert near_misses("KA21GH1358", stolen, 1) == ["KA21GH1357"]
    assert near_misses("TN09ZZ0000", stolen, 1) == []


def test_nearest_place_and_distance():
    a = SimpleNamespace(name="A", lat=12.97, lon=77.59)
    b = SimpleNamespace(name="B", lat=13.03, lon=77.60)
    place, km = nearest(13.02, 77.60, [a, b])
    assert place is b and km < 2


def test_nearest_needs_at_least_one_place():
    with pytest.raises(ValueError):
        nearest(0, 0, [])
