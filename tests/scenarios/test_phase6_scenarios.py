"""Phase 6 exit criteria: S14, S16, status history and audit, evidence retention.

Real flow against PostgreSQL, rolled back afterwards.
"""

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import (
    Alert,
    AuditLog,
    Camera,
    Evidence,
    PoliceStation,
    StatusHistory,
    User,
    Vehicle,
    VehicleReport,
)
from app.domain.states import AlertStatus as A
from app.domain.states import RecoveryStatus as R
from app.domain.states import ReportType, Role
from app.pipeline.plate_validator import VoteStatus
from app.services import alerts as alerts_module
from app.services import cases
from app.services import evidence as evidence_module
from app.services.audit import verify_chain
from app.services.cases import NotFound, PermissionDenied, RuleViolation
from app.services.retention import purge_expired
from app.services.sightings import PlateEvent, record_sighting

pytestmark = pytest.mark.db

STOLEN = "TS12AB1001"
OTHER = "TS12CD2002"
UNREGISTERED = "TS12ZZ9999"
PASSWORD = "Test-pass-123"  # a test value, only used in rolled-back tests


@pytest.fixture
def world(session, tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_module, "EVIDENCE_DIR", tmp_path)
    alerts_module.clear_station_cache()
    session.add(PoliceStation(station_id="T-PS", name="Test PS", lat=20, lon=80,
                              email="ps@test.local"))  # fmt: skip
    session.flush()
    session.add(Camera(camera_id="T-CAM", station_id="T-PS", name="Cam", lat=20, lon=80,
                       source_type="PHONE_STREAM"))  # fmt: skip
    for plate in (STOLEN, OTHER):
        session.add(Vehicle(plate_no=plate, vehicle_type="CAR", make="T", model="T",
                            colour_family="RED", owner_name="Test"))  # fmt: skip
    session.flush()
    team = SimpleTeam(
        officer=make_user(session, "t6_officer", Role.POLICE_OFFICER),
        viewer=make_user(session, "t6_viewer", Role.VIEWER),
        operator=make_user(session, "t6_operator", Role.CAMERA_OPERATOR),
        admin=make_user(session, "t6_admin", Role.ADMIN),
    )
    session.add(VehicleReport(plate_no=STOLEN, report_type="STOLEN", fir_ref="FIR-T6",
                              reported_at=datetime.now(UTC) - timedelta(hours=5),
                              reported_place="Test"))  # fmt: skip
    session.flush()
    yield team
    alerts_module.clear_station_cache()


PASSWORD_HASH = hash_password(PASSWORD)  # bcrypt is slow, so hash once for all tests


def make_user(session, username, role):
    user = User(username=username, password_hash=PASSWORD_HASH, role=role)
    session.add(user)
    session.flush()
    return user


class SimpleTeam:
    def __init__(self, **users):
        self.__dict__.update(users)


def see(session, plate, days_ago=0.0, with_images=True):
    img = np.full((40, 80, 3), 90, np.uint8) if with_images else None
    result = record_sighting(
        session,
        PlateEvent(camera_id="T-CAM", status=VoteStatus.ACCEPTED,
                   observed_at=time.time() - days_ago * 86400, plate=plate,
                   confidence=0.9, vehicle_image=img, plate_image=img),
    )  # fmt: skip
    session.flush()
    return result


def history(session, entity_id):
    return session.scalars(
        select(StatusHistory).where(StatusHistory.entity_id == entity_id)
        .order_by(StatusHistory.seq)
    ).all()  # fmt: skip


def audit_actions(session):
    return [a.action for a in session.scalars(select(AuditLog).order_by(AuditLog.seq))]


def stolen_report(session):
    return session.scalar(select(VehicleReport).where(VehicleReport.plate_no == STOLEN))


# ------------------------------------------------------------------- S14
def test_s14_officer_takes_a_stolen_report_to_recovery_with_notes(session, world):
    changes_before = audit_actions(session).count("REPORT_STATUS_CHANGED")
    see(session, STOLEN)  # the camera sees it: REPORTED -> DETECTED automatically
    report = stolen_report(session)
    assert report.recovery_status == R.DETECTED
    steps = [
        (R.UNDER_INVESTIGATION, "Patrol sent to the junction", "Central Junction"),
        (R.RECOVERED, "Vehicle found, owner informed", "Yard 4"),
        (R.CLOSED, "Case closed", None),
    ]
    for status, note, place in steps:
        cases.change_recovery_status(session, world.officer, report.report_id,
                                     status, note, place)  # fmt: skip
    assert report.recovery_status == R.CLOSED
    rows = history(session, report.report_id)
    assert [(h.from_status, h.to_status) for h in rows] == [
        ("REPORTED", "DETECTED"),
        ("DETECTED", "UNDER_INVESTIGATION"),
        ("UNDER_INVESTIGATION", "RECOVERED"),
        ("RECOVERED", "CLOSED"),
    ]
    by_officer = [h for h in rows if h.user_id == world.officer.user_id]
    assert [h.note for h in by_officer][:2] == [
        "Patrol sent to the junction",
        "Vehicle found, owner informed",
    ]
    assert by_officer[0].location == "Central Junction"
    audited = audit_actions(session).count("REPORT_STATUS_CHANGED") - changes_before
    assert audited == 4  # the automatic change and the three by the officer
    assert verify_chain(session) == (True, None)


def test_disallowed_recovery_transition_and_missing_note_are_rejected(session, world):
    report = stolen_report(session)  # still REPORTED
    with pytest.raises(RuleViolation):
        cases.change_recovery_status(session, world.officer, report.report_id,
                                     R.RECOVERED, "skipping steps")  # fmt: skip
    with pytest.raises(RuleViolation):
        cases.change_recovery_status(session, world.officer, report.report_id,
                                     R.DETECTED, "   ")  # fmt: skip
    assert report.recovery_status == R.REPORTED
    assert history(session, report.report_id) == []


# ------------------------------------------------------------------- S16
@pytest.mark.parametrize("who", ["viewer", "operator"])
def test_s16_viewer_and_operator_cannot_change_a_recovery_status(session, world, who):
    see(session, STOLEN)
    report = stolen_report(session)
    before = len(history(session, report.report_id))
    with pytest.raises(PermissionDenied):
        cases.change_recovery_status(session, getattr(world, who), report.report_id,
                                     R.UNDER_INVESTIGATION, "trying")  # fmt: skip
    assert report.recovery_status == R.DETECTED
    assert len(history(session, report.report_id)) == before
    denied = session.scalars(
        select(AuditLog).where(AuditLog.action == "ACCESS_DENIED")
    ).all()
    assert denied[-1].user_id == getattr(world, who).user_id
    assert denied[-1].details["action"] == "CHANGE_RECOVERY_STATUS"


def test_inactive_user_is_refused_even_with_the_right_role(session, world):
    world.officer.is_active = False
    report = stolen_report(session)
    with pytest.raises(PermissionDenied):
        cases.change_recovery_status(session, world.officer, report.report_id,
                                     R.DETECTED, "n")  # fmt: skip


# ------------------------------------------------------------ alert workflow
def test_alert_goes_through_the_workflow_with_history_and_audit(session, world):
    changes_before = audit_actions(session).count("ALERT_STATUS_CHANGED")
    [alert] = see(session, STOLEN).alerts
    assert alert.status == A.NEW
    for status, note in [(A.ACKNOWLEDGED, "Seen by control room"),
                         (A.UNDER_INVESTIGATION, "Unit dispatched"),
                         (A.CLOSED_CONFIRMED, "Vehicle confirmed stolen")]:  # fmt: skip
        cases.change_alert_status(session, world.officer, alert.alert_id, status, note)
    assert alert.status == A.CLOSED_CONFIRMED
    rows = history(session, alert.alert_id)
    assert [h.to_status for h in rows] == ["ACKNOWLEDGED", "UNDER_INVESTIGATION", "CLOSED_CONFIRMED"]  # fmt: skip
    assert all(h.user_id == world.officer.user_id and h.note for h in rows)
    assert audit_actions(session).count("ALERT_STATUS_CHANGED") - changes_before == 3
    with pytest.raises(RuleViolation):  # closed is final
        cases.change_alert_status(session, world.officer, alert.alert_id,
                                  A.NEW, "reopen")  # fmt: skip


def test_viewer_cannot_change_an_alert_and_unknown_alert_is_not_found(session, world):
    [alert] = see(session, STOLEN).alerts
    with pytest.raises(PermissionDenied):
        cases.change_alert_status(session, world.viewer, alert.alert_id,
                                  A.ACKNOWLEDGED, "x")  # fmt: skip
    assert alert.status == A.NEW
    with pytest.raises(NotFound):
        cases.change_alert_status(session, world.officer, "nope", A.ACKNOWLEDGED, "x")


# ------------------------------------------------------------ create reports
def test_new_report_is_matched_from_the_next_sighting_on(session, world):
    assert (
        see(session, OTHER, days_ago=0.01).alerts == []
    )  # seen 14 min ago, not reported
    report = cases.create_report(session, world.officer, OTHER.lower(),
                                 ReportType.MISSING, "FIR-NEW", "Market road")  # fmt: skip
    assert report.recovery_status == R.REPORTED and report.plate_no == OTHER
    result = see(session, OTHER)
    assert [a.alert_type for a in result.alerts] == ["MISSING_VEHICLE"]
    assert "REPORT_CREATED" in audit_actions(session)


def test_report_rules(session, world):
    with pytest.raises(NotFound):  # only vehicles in the registry
        cases.create_report(session, world.officer, UNREGISTERED,
                            ReportType.STOLEN, "F", "P")  # fmt: skip
    with pytest.raises(RuleViolation):  # STOLEN already open for this plate
        cases.create_report(session, world.officer, STOLEN, ReportType.STOLEN, "F", "P")
    with pytest.raises(PermissionDenied):
        cases.create_report(session, world.viewer, OTHER, ReportType.STOLEN, "F", "P")
    assert cases.create_report(session, world.admin, OTHER, ReportType.STOLEN,
                               "F2", "Place").plate_no == OTHER  # admins may file  # fmt: skip


def test_case_stats_count_statuses_and_time_to_detection(session, world):
    before = cases.case_stats(session)
    see(session, STOLEN)  # reported 5 hours ago, detected now
    after = cases.case_stats(session)
    assert after["by_status"]["DETECTED"] == before["by_status"]["DETECTED"] + 1
    assert after["by_status"]["REPORTED"] == before["by_status"]["REPORTED"] - 1
    assert after["median_hours_to_detection"] is not None


# ------------------------------------------------------------- retention
def evidence_of(session, sighting):
    return session.scalars(
        select(Evidence).where(Evidence.sighting_id == sighting.sighting_id)
    ).all()


def test_expired_evidence_is_purged_but_recent_evidence_is_kept(session, world):
    old = see(session, OTHER, days_ago=40).sighting  # registered, no report: no alert
    new = see(session, OTHER, days_ago=1).sighting
    old_files = [Path(e.path) for e in evidence_of(session, old)]
    assert old_files and all(f.exists() for f in old_files)
    result = purge_expired(session)
    assert result["purged"] == 2
    assert not any(f.exists() for f in old_files)  # deleted from disk
    for e in evidence_of(session, old):
        assert e.purged_at is not None and e.sha256  # row and hash are kept
    assert all(e.purged_at is None for e in evidence_of(session, new))
    assert "EVIDENCE_PURGED" in audit_actions(session)


def test_evidence_on_an_open_alert_is_kept_even_when_expired(session, world):
    sighting = see(session, STOLEN, days_ago=40).sighting  # raises an open alert
    result = purge_expired(session)
    assert result["kept_open_alert"] == 2 and result["purged"] == 0
    assert all(Path(e.path).exists() for e in evidence_of(session, sighting))


def test_evidence_of_an_open_case_is_kept_after_the_alert_is_closed(session, world):
    see(session, STOLEN, days_ago=40)
    [alert] = session.scalars(select(Alert).where(Alert.plate_no == STOLEN)).all()
    for status in (A.UNDER_INVESTIGATION, A.CLOSED_CONFIRMED):
        cases.change_alert_status(session, world.officer, alert.alert_id, status, "n")
    result = purge_expired(session)  # alert closed, but the report is still open
    assert result["kept_open_case"] == 2 and result["purged"] == 0


def test_evidence_is_purged_once_the_alert_and_the_case_are_both_closed(session, world):
    sighting = see(session, STOLEN, days_ago=40).sighting
    [alert] = session.scalars(select(Alert).where(Alert.plate_no == STOLEN)).all()
    for status in (A.UNDER_INVESTIGATION, A.CLOSED_CONFIRMED):
        cases.change_alert_status(session, world.officer, alert.alert_id, status, "n")
    report = stolen_report(session)
    for status in (R.UNDER_INVESTIGATION, R.RECOVERED, R.CLOSED):
        cases.change_recovery_status(
            session, world.officer, report.report_id, status, "n"
        )
    assert purge_expired(session)["purged"] == 2
    assert all(e.purged_at for e in evidence_of(session, sighting))


def test_dry_run_deletes_nothing(session, world):
    old = see(session, OTHER, days_ago=40).sighting
    files = [Path(e.path) for e in evidence_of(session, old)]
    assert purge_expired(session, dry_run=True)["purged"] == 2
    assert all(f.exists() for f in files)
    assert all(e.purged_at is None for e in evidence_of(session, old))


def test_purging_twice_does_nothing_the_second_time(session, world):
    see(session, OTHER, days_ago=40)
    assert purge_expired(session)["purged"] == 2
    assert purge_expired(session)["purged"] == 0


def test_a_missing_file_is_still_marked_purged(session, world):
    old = see(session, OTHER, days_ago=40).sighting
    for e in evidence_of(session, old):
        Path(e.path).unlink()
    result = purge_expired(session)
    assert result["purged"] == 2 and result["missing_file"] == 2
