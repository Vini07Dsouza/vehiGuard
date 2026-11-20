"""Phase 5 exit criteria: S05 (HIGH), S06 (MEDIUM), S07 (LOW), S11, UNKNOWN safety.

Real flow against PostgreSQL, rolled back afterwards. T-A to T-C is about
37.8 km, so the same plate seen at both a few minutes apart is an impossible
journey.
"""

from datetime import UTC, datetime

import numpy as np
import pytest
from sqlalchemy import select

from app.db.models import Camera, PoliceStation, Vehicle, VehicleReport
from app.domain.states import ColourFamily as C
from app.domain.states import VehicleType as V
from app.pipeline.plate_validator import VoteStatus
from app.services import alerts as alerts_module
from app.services import evidence as evidence_module
from app.services.alerts import alert_payload
from app.services.sightings import PlateEvent, record_sighting

pytestmark = pytest.mark.db

WHITE_CAR = "TS11AA1001"  # registered: white car
RED_CAR = "TS11BB2002"  # registered: red car
STOLEN_CAR = "TS11CC3003"  # registered: white car, reported stolen
T0 = datetime(2026, 11, 21, 10, 0, 0, tzinfo=UTC).timestamp()
MIN = 60.0


@pytest.fixture
def world(session, tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_module, "EVIDENCE_DIR", tmp_path)
    alerts_module.clear_station_cache()
    session.add(PoliceStation(station_id="T-PS", name="Test PS", lat=20.0, lon=80.0,
                              email="ps@test.local"))  # fmt: skip
    session.flush()
    for cam, lat in (("T-A", 20.00), ("T-C", 20.34)):
        session.add(Camera(camera_id=cam, station_id="T-PS", name=f"Camera {cam}",
                           lat=lat, lon=80.0, source_type="PHONE_STREAM"))  # fmt: skip
    for plate, colour in (
        (WHITE_CAR, C.WHITE_SILVER_GREY),
        (RED_CAR, C.RED),
        (STOLEN_CAR, C.WHITE_SILVER_GREY),
    ):
        session.add(Vehicle(plate_no=plate, vehicle_type=V.CAR, make="T", model="T",
                            colour_family=colour, owner_name="Test"))  # fmt: skip
    session.add(VehicleReport(plate_no=STOLEN_CAR, report_type="STOLEN", fir_ref="FIR-T",
                              reported_at=datetime.now(UTC), reported_place="Test"))  # fmt: skip
    session.flush()
    yield
    alerts_module.clear_station_cache()


def see(session, camera, plate, minutes, vtype=V.CAR, colour=C.RED):
    img = np.full((40, 80, 3), 120, np.uint8)
    result = record_sighting(
        session,
        PlateEvent(camera_id=camera, status=VoteStatus.ACCEPTED,
                   observed_at=T0 + minutes * MIN, plate=plate, confidence=0.9,
                   vehicle_type=vtype, colour_family=colour,
                   vehicle_image=img, plate_image=img),
    )  # fmt: skip
    session.flush()
    return result


def kinds(result):
    return sorted((a.alert_type, a.severity) for a in result.alerts)


def test_s05_clone_with_a_different_looking_vehicle_is_high(session, world):
    see(session, "T-A", RED_CAR, 0, V.CAR, C.RED)
    second = see(
        session, "T-C", RED_CAR, 6, V.CAR, C.WHITE_SILVER_GREY
    )  # looks different
    assert kinds(second) == [("SUSPECTED_CLONE", "HIGH")]  # one alert, not two
    clone = next(a for a in second.alerts if a.alert_type == "SUSPECTED_CLONE")
    assert clone.severity == "HIGH"
    assert {"IMPOSSIBLE_JOURNEY", "SIGHTING_APPEARANCE_MISMATCH"} <= set(
        clone.reason_codes
    )
    assert "REGISTRY_APPEARANCE_MISMATCH" in clone.reason_codes  # registry says red too


def test_s06_clone_with_a_similar_looking_vehicle_is_medium(session, world):
    see(session, "T-A", RED_CAR, 0, V.CAR, C.RED)
    second = see(session, "T-C", RED_CAR, 6, V.CAR, C.RED)  # same look as registry
    assert kinds(second) == [("SUSPECTED_CLONE", "MEDIUM")]


def test_s07_white_car_plate_on_a_red_motorcycle_is_low_at_one_camera(session, world):
    result = see(session, "T-A", WHITE_CAR, 0, V.MOTORCYCLE, C.RED)
    assert result.sighting.outcome == "APPEARANCE_MISMATCH"
    assert kinds(result) == [("APPEARANCE_MISMATCH", "LOW")]
    assert "REGISTRY_APPEARANCE_MISMATCH" in result.sighting.reason_codes
    payload = alert_payload(session, result.alerts[0])
    assert payload["registry"]["colour_family"] == "WHITE_SILVER_GREY"
    assert (payload["vehicle_type"], payload["colour_family"]) == ("MOTORCYCLE", "RED")


def test_low_alert_is_dashboard_only_no_email(session, world):
    from app.db.models import Outbox

    result = see(session, "T-A", WHITE_CAR, 0, V.MOTORCYCLE, C.RED)
    queued = session.scalars(
        select(Outbox).where(Outbox.alert_id == result.alerts[0].alert_id)
    ).all()
    assert queued == []  # FR-ALR-03: LOW alerts are not emailed


def test_s11_poor_light_gives_unknown_and_no_appearance_alert(session, world):
    result = see(session, "T-A", WHITE_CAR, 0, V.UNKNOWN, C.UNKNOWN)
    assert result.sighting.outcome == "PASS" and result.alerts == []


def test_unknown_never_causes_a_mismatch_even_on_a_clone_journey(session, world):
    see(session, "T-A", RED_CAR, 0, V.CAR, C.RED)
    second = see(session, "T-C", RED_CAR, 6, V.UNKNOWN, C.UNKNOWN)  # night, unreadable
    assert kinds(second) == [("SUSPECTED_CLONE", "MEDIUM")]  # IJ only, not HIGH
    assert "SIGHTING_APPEARANCE_MISMATCH" not in second.sighting.reason_codes


def test_catch_all_colour_is_not_a_mismatch(session, world):
    result = see(session, "T-A", WHITE_CAR, 0, V.CAR, C.OTHER)
    assert result.alerts == []


def test_clone_when_only_the_registry_disagrees_is_high(session, world):
    """Registry says white; the same plate is seen red at both cameras (RM, no AM)."""
    see(session, "T-A", WHITE_CAR, 0, V.CAR, C.RED)
    second = see(session, "T-C", WHITE_CAR, 6, V.CAR, C.RED)
    clone = next(a for a in second.alerts if a.alert_type == "SUSPECTED_CLONE")
    assert clone.severity == "HIGH"
    assert "SIGHTING_APPEARANCE_MISMATCH" not in clone.reason_codes
    assert "REGISTRY_APPEARANCE_MISMATCH" in clone.reason_codes


def test_stolen_vehicle_that_looks_different_keeps_high_and_adds_reason(session, world):
    result = see(session, "T-A", STOLEN_CAR, 0, V.MOTORCYCLE, C.RED)
    stolen = next(a for a in result.alerts if a.alert_type == "STOLEN_VEHICLE")
    assert stolen.severity == "HIGH"
    assert "APPEARANCE_MISMATCH" in stolen.reason_codes  # plate may be copied
    assert report_status(session) == "DETECTED"


def report_status(session):
    return session.scalar(
        select(VehicleReport.recovery_status).where(
            VehicleReport.plate_no == STOLEN_CAR
        )
    )
