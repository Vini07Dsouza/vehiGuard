"""REST endpoints for sign-in, alerts and stolen/missing reports (Phase 6).

Base path /api/v1. Every endpoint except login and health needs a token, and
every change checks the permission matrix (app/domain/permissions.py).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session, require
from app.core.config import load_yaml
from app.core.security import create_access_token
from app.db.models import (
    Alert,
    Camera,
    PoliceStation,
    Sighting,
    StatusHistory,
    User,
    VehicleReport,
)
from app.db.repositories import UserRepository
from app.domain.permissions import Action
from app.domain.states import (
    ALERT_TRANSITIONS,
    RECOVERY_TRANSITIONS,
    AlertStatus,
    AlertType,
    HistoryEntity,
    RecoveryStatus,
    Severity,
)
from app.schemas.cases import (
    AlertOut,
    AlertStatusRequest,
    LoginRequest,
    ReportCreate,
    ReportOut,
    ReportStatusRequest,
    TokenOut,
)
from app.services import cases
from app.services.alerts import alert_payload
from app.services.audit import append_audit

router = APIRouter(prefix="/api/v1")


def _http(exc: Exception) -> HTTPException:
    """Business-rule errors become clean HTTP errors."""
    if isinstance(exc, cases.NotFound):
        return HTTPException(404, str(exc))
    return HTTPException(409, str(exc))


# ------------------------------------------------------------------- sign in
@router.post("/auth/login", response_model=TokenOut, tags=["auth"])
def login(body: LoginRequest, session: Session = Depends(get_session)) -> TokenOut:
    user = UserRepository(session).authenticate(body.username, body.password)
    if user is None:
        append_audit(session, "LOGIN_FAILED", "users", details={"username": body.username[:50]})  # fmt: skip
        session.commit()
        raise HTTPException(401, "Wrong username or password")
    append_audit(session, "LOGIN", "users", user.user_id, user_id=user.user_id)
    session.commit()
    return TokenOut(
        access_token=create_access_token(user.user_id, str(user.role)),
        role=str(user.role),
        expires_in_minutes=load_yaml("settings.yaml")["security"][
            "access_token_minutes"
        ],
    )


# -------------------------------------------------------------------- alerts
@router.get("/alerts", tags=["alerts"])
def list_alerts(
    status: AlertStatus | None = None,
    alert_type: AlertType | None = None,
    severity: Severity | None = None,
    station_id: str | None = Query(None, max_length=32),
    plate: str | None = Query(None, max_length=15),
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require(Action.VIEW_ALERTS)),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Alerts with filters (FR-DSH-03), newest first, with camera and station names."""
    stmt = (
        select(Alert, Sighting, Camera.name, PoliceStation.name)
        .join(Sighting, Sighting.sighting_id == Alert.sighting_id)
        .join(Camera, Camera.camera_id == Sighting.camera_id)
        .join(PoliceStation, PoliceStation.station_id == Alert.station_id)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    for column, value in ((Alert.status, status), (Alert.alert_type, alert_type),
                          (Alert.severity, severity), (Alert.station_id, station_id)):  # fmt: skip
        if value:
            stmt = stmt.where(column == value)
    if plate:
        stmt = stmt.where(Alert.plate_no.like(f"{plate.strip().upper()}%"))
    if since:
        stmt = stmt.where(Alert.created_at >= since)
    if until:
        stmt = stmt.where(Alert.created_at <= until)
    return [
        {
            "alert_id": a.alert_id, "alert_type": a.alert_type, "severity": a.severity,
            "plate_no": a.plate_no, "status": a.status, "station_id": a.station_id,
            "station_name": station, "camera_name": camera, "merged_count": a.merged_count,
            "reason_codes": a.reason_codes, "created_at": a.created_at,
            "observed_at": sighting.observed_at,
        }
        for a, sighting, camera, station in session.execute(stmt)
    ]  # fmt: skip


@router.get("/alerts/{alert_id}", tags=["alerts"])
def alert_detail(
    alert_id: str,
    _: User = Depends(require(Action.VIEW_ALERTS)),
    session: Session = Depends(get_session),
) -> dict:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    history = session.scalars(
        select(StatusHistory)
        .where(StatusHistory.entity_type == HistoryEntity.ALERT,
               StatusHistory.entity_id == alert_id)
        .order_by(StatusHistory.seq)
    ).all()  # fmt: skip
    return {
        **alert_payload(session, alert),
        "status": alert.status,
        "allowed_next_statuses": sorted(ALERT_TRANSITIONS[AlertStatus(alert.status)]),
        "history": [
            {"from": h.from_status, "to": h.to_status, "note": h.note,
             "user_id": h.user_id, "ts": h.ts.isoformat()}
            for h in history
        ],
    }  # fmt: skip


@router.post("/alerts/{alert_id}/status", response_model=AlertOut, tags=["alerts"])
def set_alert_status(
    alert_id: str,
    body: AlertStatusRequest,
    user: User = Depends(require(Action.CHANGE_ALERT_STATUS)),
    session: Session = Depends(get_session),
):
    try:
        alert = cases.change_alert_status(
            session, user, alert_id, body.status, body.note
        )
    except (cases.NotFound, cases.RuleViolation) as exc:
        raise _http(exc) from exc
    session.commit()
    return alert


# ------------------------------------------------------------------- reports
def _report_row(r: VehicleReport) -> dict:
    return {
        "report_id": r.report_id, "plate_no": r.plate_no, "report_type": r.report_type,
        "fir_ref": r.fir_ref, "reported_place": r.reported_place,
        "reported_at": r.reported_at, "recovery_status": r.recovery_status,
        "updated_at": r.updated_at,
        "allowed_next": sorted(RECOVERY_TRANSITIONS[RecoveryStatus(r.recovery_status)]),
    }  # fmt: skip


@router.get("/reports", tags=["reports"])
def list_reports(
    status: RecoveryStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require(Action.VIEW_REPORTS)),
    session: Session = Depends(get_session),
) -> list[dict]:
    stmt = select(VehicleReport).order_by(VehicleReport.reported_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(VehicleReport.recovery_status == status)
    return [_report_row(r) for r in session.scalars(stmt)]


@router.get("/reports/stats", tags=["reports"])
def report_stats(
    _: User = Depends(require(Action.VIEW_REPORTS)),
    session: Session = Depends(get_session),
) -> dict:
    return cases.case_stats(session)


@router.get("/reports/{report_id}", tags=["reports"])
def report_detail(
    report_id: str,
    _: User = Depends(require(Action.VIEW_REPORTS)),
    session: Session = Depends(get_session),
) -> dict:
    """One report with its full status history (FR-DSH-06)."""
    report = session.get(VehicleReport, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    history = session.scalars(
        select(StatusHistory)
        .where(StatusHistory.entity_type == HistoryEntity.REPORT,
               StatusHistory.entity_id == report_id)
        .order_by(StatusHistory.seq)
    ).all()  # fmt: skip
    return {
        **_report_row(report),
        "history": [
            {"from": h.from_status, "to": h.to_status, "note": h.note,
             "location": h.location, "user_id": h.user_id, "ts": h.ts.isoformat()}
            for h in history
        ],
    }  # fmt: skip


@router.post("/reports", response_model=ReportOut, status_code=201, tags=["reports"])
def create_report(
    body: ReportCreate,
    user: User = Depends(require(Action.CREATE_REPORT)),
    session: Session = Depends(get_session),
):
    try:
        report = cases.create_report(
            session, user, body.plate_no, body.report_type, body.fir_ref,
            body.reported_place, body.reported_at,
        )  # fmt: skip
    except (cases.NotFound, cases.RuleViolation) as exc:
        raise _http(exc) from exc
    session.commit()
    return report


@router.post("/reports/{report_id}/status", response_model=ReportOut, tags=["reports"])
def set_report_status(
    report_id: str,
    body: ReportStatusRequest,
    user: User = Depends(require(Action.CHANGE_RECOVERY_STATUS)),
    session: Session = Depends(get_session),
):
    try:
        report = cases.change_recovery_status(
            session, user, report_id, body.status, body.note, body.location
        )
    except (cases.NotFound, cases.RuleViolation) as exc:
        raise _http(exc) from exc
    session.commit()
    return report
