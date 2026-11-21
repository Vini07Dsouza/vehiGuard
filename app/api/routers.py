"""REST endpoints for sign-in, alerts and stolen/missing reports (Phase 6).

Base path /api/v1. Every endpoint except login and health needs a token, and
every change checks the permission matrix (app/domain/permissions.py).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session, require
from app.core.config import load_yaml
from app.core.security import create_access_token
from app.db.models import Alert, StatusHistory, User, VehicleReport
from app.db.repositories import UserRepository
from app.domain.permissions import Action
from app.domain.states import AlertStatus, HistoryEntity, RecoveryStatus
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
@router.get("/alerts", response_model=list[AlertOut], tags=["alerts"])
def list_alerts(
    status: AlertStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require(Action.VIEW_ALERTS)),
    session: Session = Depends(get_session),
):
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Alert.status == status)
    return session.scalars(stmt).all()


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
@router.get("/reports", response_model=list[ReportOut], tags=["reports"])
def list_reports(
    status: RecoveryStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require(Action.VIEW_REPORTS)),
    session: Session = Depends(get_session),
):
    stmt = select(VehicleReport).order_by(VehicleReport.reported_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(VehicleReport.recovery_status == status)
    return session.scalars(stmt).all()


@router.get("/reports/stats", tags=["reports"])
def report_stats(
    _: User = Depends(require(Action.VIEW_REPORTS)),
    session: Session = Depends(get_session),
) -> dict:
    return cases.case_stats(session)


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
