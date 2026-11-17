"""Repositories, users and the audit log against PostgreSQL (rolled back)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db.models import AuditLog, StatusHistory, Vehicle, VehicleReport
from app.db.repositories import (
    UserRepository,
    VehicleReportRepository,
    VehicleRepository,
)
from app.domain.states import RecoveryStatus, ReportType, Role
from app.services.audit import append_audit, verify_chain

pytestmark = pytest.mark.db

PLATE = "TS09ZZ0001"


def add_reported_vehicle(session, status=RecoveryStatus.REPORTED):
    VehicleRepository(session).add(
        Vehicle(
            plate_no=PLATE,
            vehicle_type="CAR",
            make="Test",
            model="Car",
            colour_family="RED",
            owner_name="Test Owner",
        )
    )
    return VehicleReportRepository(session).add(
        VehicleReport(
            plate_no=PLATE,
            report_type=ReportType.STOLEN,
            fir_ref="FIR-TEST",
            reported_at=datetime.now(UTC),
            reported_place="Test",
            recovery_status=status,
        )
    )


def test_password_is_hashed_and_checked(session):
    users = UserRepository(session)
    user = users.create("t_officer", "correct-horse", Role.POLICE_OFFICER)
    assert user.password_hash != "correct-horse"
    assert users.authenticate("t_officer", "correct-horse") == user
    assert users.authenticate("t_officer", "wrong") is None
    assert users.authenticate("nobody", "correct-horse") is None


def test_inactive_user_cannot_log_in(session):
    users = UserRepository(session)
    user = users.create("t_old", "pw-123456", Role.VIEWER)
    users.update(user, is_active=False)
    assert users.authenticate("t_old", "pw-123456") is None


def test_only_active_reports_are_matched(session):
    report = add_reported_vehicle(session)
    reports = VehicleReportRepository(session)
    assert reports.active_for_plate(PLATE) == [report]
    reports.update(report, recovery_status=RecoveryStatus.RECOVERED)
    assert reports.active_for_plate(PLATE) == []


def test_status_change_writes_history_and_audit(session):
    report = add_reported_vehicle(session)
    reports = VehicleReportRepository(session)
    reports.change_status(report, RecoveryStatus.DETECTED, None, "seen at CAM-A")
    history = session.scalars(
        select(StatusHistory).where(StatusHistory.entity_id == report.report_id)
    ).all()
    assert [(h.from_status, h.to_status) for h in history] == [("REPORTED", "DETECTED")]
    last = session.scalar(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1))
    assert last.action == "REPORT_STATUS_CHANGED"
    assert last.entity_id == report.report_id


def test_invalid_status_change_is_refused(session):
    report = add_reported_vehicle(session)
    with pytest.raises(ValueError):
        VehicleReportRepository(session).change_status(
            report, RecoveryStatus.RECOVERED, None  # REPORTED cannot jump here
        )


def test_audit_chain_links_entries(session):
    first = append_audit(session, "TEST_A", "test")
    second = append_audit(session, "TEST_B", "test", details={"n": 1})
    assert second.prev_hash == first.hash
    session.expire_all()  # read back from the database, like a later check
    assert verify_chain(session) == (True, None)


@pytest.mark.parametrize("sql", ["UPDATE {t} SET note = 'x'", "DELETE FROM {t}"])
def test_status_history_is_append_only(session, sql):
    report = add_reported_vehicle(session)
    VehicleReportRepository(session).change_status(
        report, RecoveryStatus.DETECTED, None
    )
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(text(sql.format(t="status_history")))


def test_audit_log_is_append_only(session):
    append_audit(session, "TEST", "test")
    with pytest.raises(DBAPIError, match="append-only"):
        session.execute(text("UPDATE audit_log SET action = 'CHANGED'"))
