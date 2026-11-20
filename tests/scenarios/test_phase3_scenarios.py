"""Phase 3 exit criteria: scenarios S01, S03, S04, S08, S09, S10, S12, S13.

Each test runs the real flow against PostgreSQL:
    camera event -> registry match -> decision engine -> sighting -> alert
    -> outbox -> simulated police inbox
and is rolled back afterwards. Test stations sit far from the seeded ones,
so nearest-station routing is checked too.
"""

import json
import time
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from sqlalchemy import select

from app.db.models import (
    Alert,
    Camera,
    Outbox,
    PoliceStation,
    StatusHistory,
    Vehicle,
    VehicleReport,
)
from app.domain.states import OutboxChannel
from app.notifiers.simulated import OUTAGE_FLAG, SimulatedNotifier
from app.pipeline.plate_validator import VoteStatus
from app.services import alerts as alerts_module
from app.services import evidence as evidence_module
from app.services.alerts import alert_payload
from app.services.outbox import dispatch_due
from app.services.sightings import PlateEvent, record_sighting

pytestmark = pytest.mark.db

REGISTERED = "TS09AB1001"
STOLEN = "TS09CD2002"
MISSING = "TS09EF3003"
UNKNOWN = "TS09XY9999"
ONE_OFF_STOLEN = "TS09CD2008"  # one character from STOLEN


@pytest.fixture
def world(session, tmp_path, monkeypatch):
    """Two stations, one camera next to the second, vehicles and reports."""
    monkeypatch.setattr(evidence_module, "EVIDENCE_DIR", tmp_path / "evidence")
    alerts_module.clear_station_cache()
    session.add_all(
        [
            PoliceStation(station_id="T-PS1", name="Test North", lat=20.30,
                          lon=80.00, email="north@test.local"),
            PoliceStation(station_id="T-PS2", name="Test South", lat=20.00,
                          lon=80.00, email="south@test.local"),
        ]
    )  # fmt: skip
    session.flush()
    session.add(
        Camera(camera_id="T-CAM", station_id="T-PS1", name="Test Junction",
               lat=20.01, lon=80.01, source_type="PHONE_STREAM")
    )  # fmt: skip
    for plate in (REGISTERED, STOLEN, MISSING):
        session.add(
            Vehicle(plate_no=plate, vehicle_type="CAR", make="T", model="T",
                    colour_family="WHITE_SILVER_GREY", owner_name="Test Owner")
        )  # fmt: skip
    session.flush()
    now = datetime.now(UTC)
    for plate, kind in ((STOLEN, "STOLEN"), (MISSING, "MISSING")):
        session.add(
            VehicleReport(plate_no=plate, report_type=kind, fir_ref=f"FIR-{kind}",
                          reported_at=now - timedelta(days=2), reported_place="Test")
        )  # fmt: skip
    session.flush()
    yield tmp_path
    alerts_module.clear_station_cache()


def see(session, plate, status=VoteStatus.ACCEPTED, at=None):
    img = np.full((60, 120, 3), 200, np.uint8)
    event = PlateEvent(
        camera_id="T-CAM",
        status=status,
        observed_at=at or time.time(),
        plate=plate,
        confidence=0.93 if plate else None,
        vehicle_image=img,
        plate_image=img,
        stage_ms={"total": 250.0},
    )
    result = record_sighting(session, event)
    session.flush()
    return result


def alerts_for(session, plate):
    return session.scalars(select(Alert).where(Alert.plate_no == plate)).all()


def test_s01_registered_vehicle_passes(session, world):
    result = see(session, REGISTERED)
    assert result.sighting.outcome == "PASS"
    assert result.alerts == [] and alerts_for(session, REGISTERED) == []


def test_s03_stolen_vehicle_raises_high_alert_and_detects_report(session, world):
    result = see(session, STOLEN)
    assert result.sighting.outcome == "STOLEN_MATCH"
    [alert] = result.alerts
    assert (alert.alert_type, alert.severity) == ("STOLEN_VEHICLE", "HIGH")
    report = session.scalar(
        select(VehicleReport).where(VehicleReport.plate_no == STOLEN)
    )
    assert report.recovery_status == "DETECTED"
    history = session.scalars(
        select(StatusHistory).where(StatusHistory.entity_id == report.report_id)
    ).all()
    assert [(h.from_status, h.to_status) for h in history] == [("REPORTED", "DETECTED")]


def test_s04_missing_vehicle_raises_high_alert(session, world):
    result = see(session, MISSING)
    assert result.sighting.outcome == "MISSING_MATCH"
    assert [(a.alert_type, a.severity) for a in result.alerts] == [
        ("MISSING_VEHICLE", "HIGH")
    ]


def test_s08_unknown_plate_is_logged_without_alert(session, world):
    result = see(session, UNKNOWN)
    assert result.sighting.outcome == "UNKNOWN_PLATE"
    assert result.alerts == []


def test_s09_no_plate_is_logged_without_alert(session, world):
    result = see(session, None, status=VoteStatus.NO_PLATE)
    assert result.sighting.outcome == "NO_PLATE"
    assert result.alerts == []


def test_s10_one_character_off_is_review_only(session, world):
    result = see(session, ONE_OFF_STOLEN)
    assert result.sighting.outcome == "POSSIBLE_MATCH"
    assert result.decision.review_item is True
    assert result.alerts == []
    assert "POSSIBLE_MATCH" in result.sighting.reason_codes


def test_s12_repeat_within_cooldown_merges_into_one_alert(session, world):
    first = see(session, STOLEN)
    second = see(session, STOLEN, at=time.time() + 60)
    [alert] = alerts_for(session, STOLEN)
    assert first.alerts[0] is second.alerts[0] is alert
    assert alert.merged_count == 2
    assert alert.merged_sighting_ids == [second.sighting.sighting_id]
    emails = session.scalars(select(Outbox).where(Outbox.alert_id == alert.alert_id))
    assert len(emails.all()) == 1  # the repeat sends no second email


def test_alert_has_plate_location_time_evidence_and_nearest_station(session, world):
    [alert] = see(session, STOLEN).alerts
    payload = alert_payload(session, alert)
    assert payload["plate"] == STOLEN
    assert payload["camera"]["lat"] == 20.01 and payload["observed_at"]
    # camera belongs to T-PS1, but T-PS2 is nearer: alerts go to the nearest
    assert payload["station"]["id"] == "T-PS2"
    assert {e["kind"] for e in payload["evidence"]} == {"VEHICLE_FRAME", "PLATE_CROP"}
    assert payload["report"]["status"] == "DETECTED"


def test_s13_alert_is_delivered_after_network_outage(session, world):
    inbox = world / "inbox"
    inbox.mkdir()
    notifiers = {OutboxChannel.SIMULATED: SimulatedNotifier(inbox)}
    [alert] = see(session, STOLEN).alerts
    [item] = session.scalars(select(Outbox).where(Outbox.alert_id == alert.alert_id))
    item.channel = OutboxChannel.SIMULATED  # independent of ALERT_MODE in .env
    start = datetime.now(UTC)

    (inbox / OUTAGE_FLAG).touch()  # network down
    dispatch_due(session, start, notifiers)
    assert (item.status, item.attempts) == ("RETRYING", 1)
    assert item.next_attempt_at == start + timedelta(seconds=5)
    dispatch_due(session, start + timedelta(seconds=1), notifiers)
    assert item.attempts == 1  # not due yet: back-off respected

    (inbox / OUTAGE_FLAG).unlink()  # network restored
    dispatch_due(session, start + timedelta(seconds=6), notifiers)
    assert item.status == "DELIVERED"
    [line] = (inbox / "south@test.local.jsonl").read_text().splitlines()
    assert json.loads(line)["plate"] == STOLEN


def test_delivery_gives_up_after_max_attempts(session, world):
    inbox = world / "inbox"
    inbox.mkdir()
    (inbox / OUTAGE_FLAG).touch()
    notifiers = {OutboxChannel.SIMULATED: SimulatedNotifier(inbox)}
    [alert] = see(session, MISSING).alerts
    [item] = session.scalars(select(Outbox).where(Outbox.alert_id == alert.alert_id))
    item.channel = OutboxChannel.SIMULATED
    t = datetime.now(UTC)
    for _ in range(5):
        dispatch_due(session, t, notifiers)
        t = t + timedelta(minutes=10)
    assert (item.status, item.attempts) == ("FAILED", 5)
