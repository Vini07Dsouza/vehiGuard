"""Phase 4 exit criteria: S02, S05, S06, S17, no false clones, timing.

Real flow against PostgreSQL, rolled back afterwards. Test cameras sit far
from the seeded ones: T-A to T-B about 6.7 km, T-A to T-C about 37.8 km.
"""

import time
from datetime import UTC, datetime

import numpy as np
import pytest
from sqlalchemy import select

from app.db.models import Camera, Evidence, PoliceStation, Sighting, Vehicle
from app.pipeline.plate_validator import VoteStatus
from app.services import alerts as alerts_module
from app.services import evidence as evidence_module
from app.services.alerts import alert_payload
from app.services.clones import find_clone_signal
from app.services.sightings import PlateEvent, record_sighting

pytestmark = pytest.mark.db

GENUINE = "TS10AB1111"  # S02: one car driving A -> B
CLONED = "TS10CD2222"  # S05/S06: same plate on two vehicles, A and C
UNKNOWN_CLONE = "TS10EF3333"  # not registered, still analysed (FR-REG-05)
T0 = datetime(2026, 11, 20, 10, 0, 0, tzinfo=UTC).timestamp()
MIN = 60.0


@pytest.fixture
def world(session, tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_module, "EVIDENCE_DIR", tmp_path)
    alerts_module.clear_station_cache()
    session.add(PoliceStation(station_id="T-PS", name="Test PS", lat=20.0, lon=80.0,
                              email="ps@test.local"))  # fmt: skip
    session.flush()
    for cam, lat in (("T-A", 20.00), ("T-B", 20.06), ("T-C", 20.34)):
        session.add(Camera(camera_id=cam, station_id="T-PS", name=f"Camera {cam}",
                           lat=lat, lon=80.0, source_type="PHONE_STREAM"))  # fmt: skip
    for plate in (GENUINE, CLONED):
        session.add(Vehicle(plate_no=plate, vehicle_type="CAR", make="T", model="T",
                            colour_family="RED", owner_name="Test"))  # fmt: skip
    session.flush()
    yield
    alerts_module.clear_station_cache()


def see(session, camera, plate, at, conf=0.9, status=VoteStatus.ACCEPTED, shade=100):
    img = np.full((40, 80, 3), shade, np.uint8)
    result = record_sighting(
        session,
        PlateEvent(camera_id=camera, status=status, observed_at=at, plate=plate,
                   confidence=conf, vehicle_image=img, plate_image=img),
    )  # fmt: skip
    session.flush()
    return result


def clone_alerts(result):
    return [a for a in result.alerts if a.alert_type == "SUSPECTED_CLONE"]


def test_s02_plausible_journey_is_not_a_clone(session, world):
    see(session, "T-A", GENUINE, T0)
    second = see(session, "T-B", GENUINE, T0 + 10 * MIN)  # 6.7 km in 10 min
    assert second.sighting.outcome == "PASS"
    assert clone_alerts(second) == []
    assert second.clone.checked and not second.clone.impossible_journey


def test_s06_impossible_journey_raises_suspected_clone(session, world):
    first = see(session, "T-A", CLONED, T0)
    second = see(session, "T-C", CLONED, T0 + 6 * MIN)  # 37.8 km in 6 min
    assert second.sighting.outcome == "SUSPECTED_CLONE"
    [alert] = clone_alerts(second)
    assert alert.severity == "MEDIUM"  # IJ only; HIGH needs an appearance signal
    assert alert.related_sighting_id == first.sighting.sighting_id
    j = alert.journey_json
    assert (j["from_camera"], j["to_camera"]) == ("T-A", "T-C")
    assert j["distance_km"] == pytest.approx(37.8, abs=0.3)
    assert j["required_speed_kmh"] == pytest.approx(378, abs=5)
    assert "IMPOSSIBLE_JOURNEY" in second.sighting.reason_codes


def test_s05_alert_carries_both_sightings_evidence(session, world):
    see(session, "T-A", CLONED, T0, shade=60)
    second = see(session, "T-C", CLONED, T0 + 6 * MIN, shade=200)
    payload = alert_payload(session, clone_alerts(second)[0])
    assert payload["camera"]["id"] == "T-C"
    assert payload["earlier_sighting"]["camera"]["id"] == "T-A"
    assert {e["kind"] for e in payload["evidence"]} == {"VEHICLE_FRAME", "PLATE_CROP"}
    assert {e["kind"] for e in payload["earlier_sighting"]["evidence"]} == {
        "VEHICLE_FRAME",
        "PLATE_CROP",
    }
    assert payload["journey"]["impossible"] is True


def test_unregistered_plate_is_still_checked_for_clones(session, world):
    see(session, "T-A", UNKNOWN_CLONE, T0)
    second = see(session, "T-C", UNKNOWN_CLONE, T0 + 2 * MIN)
    assert [a.severity for a in clone_alerts(second)] == ["MEDIUM"]


def test_s17_same_camera_repeats_make_one_sighting_and_no_clone(session, world):
    results = [see(session, "T-A", CLONED, T0 + s, conf=c)
               for s, c in ((0, 0.80), (10, 0.95), (20, 0.85))]  # fmt: skip
    assert [r.duplicate for r in results] == [False, True, True]
    rows = session.scalars(select(Sighting).where(Sighting.plate_no == CLONED)).all()
    assert len(rows) == 1
    assert rows[0].plate_conf == 0.95  # the best frame was kept
    assert len(session.scalars(select(Evidence).where(
        Evidence.sighting_id == rows[0].sighting_id)).all()) == 2  # fmt: skip
    assert all(not r.alerts for r in results)


def test_same_camera_after_cooldown_is_new_sighting_but_never_a_clone(session, world):
    see(session, "T-A", CLONED, T0)
    later = see(session, "T-A", CLONED, T0 + 5 * MIN)
    assert later.duplicate is False
    assert later.clone.checked == () and clone_alerts(later) == []


def test_low_confidence_reads_never_feed_clone_analysis(session, world):
    see(session, "T-A", None, T0, status=VoteStatus.LOW_CONFIDENCE)
    second = see(session, "T-C", CLONED, T0 + 2 * MIN)
    assert clone_alerts(second) == []


def test_sighting_outside_window_is_ignored(session, world):
    see(session, "T-A", CLONED, T0)
    second = see(session, "T-C", CLONED, T0 + 25 * 60 * MIN)  # 25 hours later
    assert clone_alerts(second) == []


def test_clone_analysis_takes_under_500_ms(session, world):
    for i in range(30):  # some history for this plate at several cameras
        see(session, ("T-A", "T-B")[i % 2], CLONED, T0 + i * 40 * MIN)
    started = time.perf_counter()
    find_clone_signal(
        session, CLONED, "T-C", datetime.fromtimestamp(T0 + 21 * 60 * MIN, UTC)
    )
    assert (time.perf_counter() - started) * 1000 < 500
