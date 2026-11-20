"""Impossible-journey rule for suspected cloned plates (architecture §8.3).

Pure functions: no database, no clock. For a new sighting s2 (camera B, t2)
and an earlier sighting s1 of the same plate (camera A, t1), A != B:

    d      = haversine(A, B)                                   # km
    dt     = |t2 - t1|                                         # hours
    limit  = MAX_PLAUSIBLE_SPEED_KMH * (dt + TIME_TOLERANCE_S / 3600)
    IJ     = (d >= MIN_CLONE_DISTANCE_KM) and (d > limit)

Multiplication instead of division, so a zero time gap is safe. Straight-line
distance and the tolerance make the rule conservative: a journey that is
possible by road is never flagged.
"""

from dataclasses import asdict, dataclass
from datetime import datetime

from app.domain.geo import haversine_km


@dataclass(frozen=True)
class CloneConfig:
    max_speed_kmh: float = 120.0
    min_distance_km: float = 1.0
    tolerance_s: float = 5.0
    window_h: float = 24.0

    @classmethod
    def from_settings(cls, cfg: dict) -> "CloneConfig":
        return cls(
            max_speed_kmh=cfg["max_plausible_speed_kmh"],
            min_distance_km=cfg["min_clone_distance_km"],
            tolerance_s=cfg["time_tolerance_s"],
            window_h=cfg["clone_window_h"],
        )


@dataclass(frozen=True)
class SightingPoint:
    sighting_id: str
    camera_id: str
    lat: float
    lon: float
    observed_at: datetime  # server time, timezone-aware


@dataclass(frozen=True)
class Journey:
    from_sighting: str
    to_sighting: str
    from_camera: str
    to_camera: str
    distance_km: float
    gap_s: float
    limit_km: float  # furthest a genuine vehicle could have travelled
    required_speed_kmh: float | None  # None when the time gap is zero
    impossible: bool

    def as_dict(self) -> dict:
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in asdict(self).items()}  # fmt: skip


@dataclass(frozen=True)
class CloneResult:
    impossible_journey: bool
    journey: Journey | None  # the most recent impossible journey, if any
    checked: tuple[Journey, ...] = ()  # every earlier sighting compared

    def journey_json(self) -> dict | None:
        if not self.journey:
            return None
        return {
            **self.journey.as_dict(),
            "other_impossible": [
                j.as_dict()
                for j in self.checked
                if j.impossible and j is not self.journey
            ],
        }


def check_journey(
    earlier: SightingPoint, later: SightingPoint, cfg: CloneConfig
) -> Journey | None:
    """Compare two sightings of one plate. None for the same camera (FR-CLN-01)."""
    if earlier.camera_id == later.camera_id:
        return None
    d = haversine_km(earlier.lat, earlier.lon, later.lat, later.lon)
    gap_s = abs((later.observed_at - earlier.observed_at).total_seconds())
    limit = cfg.max_speed_kmh * (gap_s + cfg.tolerance_s) / 3600
    return Journey(
        from_sighting=earlier.sighting_id,
        to_sighting=later.sighting_id,
        from_camera=earlier.camera_id,
        to_camera=later.camera_id,
        distance_km=d,
        gap_s=gap_s,
        limit_km=limit,
        required_speed_kmh=d / (gap_s / 3600) if gap_s > 0 else None,
        impossible=d >= cfg.min_distance_km and d > limit,
    )


def analyse(
    new: SightingPoint, earlier: list[SightingPoint], cfg: CloneConfig
) -> CloneResult:
    """Check the new sighting against earlier ones within the clone window."""
    window_s = cfg.window_h * 3600
    journeys = []
    for old in sorted(earlier, key=lambda s: s.observed_at, reverse=True):
        gap = (new.observed_at - old.observed_at).total_seconds()
        if gap < 0 or gap > window_s:  # only earlier sightings, inside the window
            continue
        journey = check_journey(old, new, cfg)
        if journey:
            journeys.append(journey)
    impossible = [j for j in journeys if j.impossible]
    # the most recent earlier sighting that gives IJ goes on the alert
    return CloneResult(
        bool(impossible), impossible[0] if impossible else None, tuple(journeys)
    )
