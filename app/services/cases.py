"""Case manager: alert workflow, recovery tracking and reports (Phase 6).

Every function takes the acting user and checks the permission matrix first.
Every status change writes a status_history row (user, time, note, optional
location) and an append-only audit entry. A refused request is audited too,
so attempts show up in the audit log (scenario S16).

The functions flush but do not commit; the caller commits.
"""

from datetime import UTC, datetime
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Alert, StatusHistory, User, Vehicle, VehicleReport
from app.db.repositories import VehicleReportRepository
from app.domain.permissions import Action, can
from app.domain.states import (
    ACTIVE_RECOVERY_STATUSES,
    ALERT_TRANSITIONS,
    AlertStatus,
    HistoryEntity,
    RecoveryStatus,
    ReportType,
)
from app.services.audit import append_audit

MAX_NOTE = 1000


class PermissionDenied(Exception):
    """The user's role is not allowed to do this."""


class RuleViolation(Exception):
    """The request breaks a business rule (bad transition, missing note...)."""


class NotFound(Exception):
    """The alert, report or vehicle does not exist."""


def authorize(session: Session, user: User, action: Action, entity: str = "") -> None:
    """Raise PermissionDenied (and audit the attempt) unless the role may act."""
    if user.is_active and can(user.role, action):
        return
    append_audit(
        session,
        "ACCESS_DENIED",
        entity or "api",
        details={"action": str(action), "role": str(user.role)},
        user_id=user.user_id,
    )
    raise PermissionDenied(f"{user.role} may not {action}")


def _clean_note(note: str | None, required: bool) -> str | None:
    note = (note or "").strip()
    if required and not note:
        raise RuleViolation("A note is required for every status change")
    if len(note) > MAX_NOTE:
        raise RuleViolation(f"Note is too long (max {MAX_NOTE} characters)")
    return note or None


# ------------------------------------------------------------ alert workflow
def change_alert_status(
    session: Session,
    user: User,
    alert_id: str,
    new_status: AlertStatus,
    note: str,
) -> Alert:
    """NEW -> ACKNOWLEDGED -> UNDER_INVESTIGATION -> CLOSED_* (FR-ALR-07).

    Only an officer can change it, so a clone is never "confirmed" automatically
    (FR-CLN-06).
    """
    authorize(session, user, Action.CHANGE_ALERT_STATUS, "alerts")
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise NotFound(f"Alert {alert_id} does not exist")
    note = _clean_note(note, required=True)
    old = AlertStatus(alert.status)
    if new_status not in ALERT_TRANSITIONS[old]:
        raise RuleViolation(f"An alert cannot go from {old} to {new_status}")
    alert.status = new_status
    session.add(
        StatusHistory(
            entity_type=HistoryEntity.ALERT,
            entity_id=alert.alert_id,
            from_status=old,
            to_status=new_status,
            user_id=user.user_id,
            note=note,
        )
    )
    append_audit(
        session,
        "ALERT_STATUS_CHANGED",
        "alerts",
        alert.alert_id,
        {"from": old, "to": new_status, "note": note},
        user_id=user.user_id,
    )
    session.flush()
    return alert


# ------------------------------------------------------------ recovery status
def change_recovery_status(
    session: Session,
    user: User,
    report_id: str,
    new_status: RecoveryStatus,
    note: str,
    location: str | None = None,
) -> VehicleReport:
    """Move a stolen/missing report along architecture section 6.3 (FR-CASE-03)."""
    authorize(session, user, Action.CHANGE_RECOVERY_STATUS, "vehicle_reports")
    report = session.get(VehicleReport, report_id)
    if report is None:
        raise NotFound(f"Report {report_id} does not exist")
    note = _clean_note(note, required=True)
    try:
        return VehicleReportRepository(session).change_status(
            report, new_status, user.user_id, note, (location or "").strip() or None
        )
    except ValueError as exc:
        raise RuleViolation(str(exc)) from exc


def create_report(
    session: Session,
    user: User,
    plate_no: str,
    report_type: ReportType,
    fir_ref: str,
    reported_place: str,
    reported_at: datetime | None = None,
) -> VehicleReport:
    """File a stolen/missing report for a vehicle in the registry (FR-CASE-04).

    It is matched against sightings from the very next sighting on.
    """
    authorize(session, user, Action.CREATE_REPORT, "vehicle_reports")
    plate_no = plate_no.strip().upper()
    if session.get(Vehicle, plate_no) is None:
        raise NotFound(f"{plate_no} is not in the vehicle registry")
    if not fir_ref.strip() or not reported_place.strip():
        raise RuleViolation("FIR reference and place are required")
    already_open = session.scalar(
        select(func.count())
        .select_from(VehicleReport)
        .where(
            VehicleReport.plate_no == plate_no,
            VehicleReport.report_type == report_type,
            VehicleReport.recovery_status.in_(ACTIVE_RECOVERY_STATUSES),
        )
    )
    if already_open:
        raise RuleViolation(f"{plate_no} already has an open {report_type} report")
    report = VehicleReport(
        plate_no=plate_no,
        report_type=report_type,
        fir_ref=fir_ref.strip(),
        reported_at=reported_at or datetime.now(UTC),
        reported_place=reported_place.strip(),
        recovery_status=RecoveryStatus.REPORTED,
    )
    session.add(report)
    session.flush()
    append_audit(
        session,
        "REPORT_CREATED",
        "vehicle_reports",
        report.report_id,
        {"plate": plate_no, "type": report_type, "fir_ref": report.fir_ref},
        user_id=user.user_id,
    )
    return report


# ------------------------------------------------------------------- numbers
def case_stats(session: Session) -> dict:
    """Reports per recovery status and time from report to detection (FR-CASE-05)."""
    counts = dict.fromkeys(RecoveryStatus, 0)
    for status, n in session.execute(
        select(VehicleReport.recovery_status, func.count()).group_by(
            VehicleReport.recovery_status
        )
    ):
        counts[RecoveryStatus(status)] = n
    first_detection = (
        select(
            StatusHistory.entity_id,
            func.min(StatusHistory.ts).label("detected_at"),
        )
        .where(
            StatusHistory.entity_type == HistoryEntity.REPORT,
            StatusHistory.to_status == RecoveryStatus.DETECTED,
        )
        .group_by(StatusHistory.entity_id)
        .subquery()
    )
    rows = session.execute(
        select(VehicleReport.reported_at, first_detection.c.detected_at).join(
            first_detection, first_detection.c.entity_id == VehicleReport.report_id
        )
    ).all()
    hours = [(d - r).total_seconds() / 3600 for r, d in rows if d >= r]
    return {
        "by_status": {str(k): v for k, v in counts.items()},
        "detected_reports": len(hours),
        "median_hours_to_detection": round(median(hours), 2) if hours else None,
    }
