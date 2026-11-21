"""Read-only endpoints for the dashboard: monitor, timeline, cameras, evidence.

Base path /api/v1. Every endpoint needs a signed-in user and checks the
permission matrix. Evidence images are served only through here, never as
public files (NFR-SEC-03).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, get_session, require
from app.core.config import get_settings
from app.db.models import (
    Alert,
    Camera,
    Evidence,
    Outbox,
    PoliceStation,
    Sighting,
    User,
    Vehicle,
    VehicleReport,
)
from app.domain.permissions import PERMISSIONS, Action, can
from app.domain.states import (
    ACTIVE_RECOVERY_STATUSES,
    OPEN_ALERT_STATUSES,
    CameraStatus,
    OutboxStatus,
    SightingOutcome,
)
from app.services import evidence as evidence_module
from app.services.retention import _file_for

router = APIRouter(prefix="/api/v1")

# A camera that has not delivered a frame for this long is shown as offline
STALE_AFTER = timedelta(seconds=30)


@router.get("/me", tags=["auth"])
def me(user: User = Depends(current_user)) -> dict:
    """Who is signed in and what they may do (the dashboard hides the rest)."""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "permissions": sorted(a for a in Action if user.role in PERMISSIONS[a]),
    }


def _evidence_by_sighting(session: Session, ids: list[str]) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {i: [] for i in ids}
    if not ids:
        return found
    for e in session.scalars(select(Evidence).where(Evidence.sighting_id.in_(ids))):
        found[e.sighting_id].append(
            {
                "evidence_id": e.evidence_id,
                "kind": e.kind,
                "purged": e.purged_at is not None,
            }
        )
    return found


def _sighting_row(s: Sighting, camera: Camera, evidence: list[dict]) -> dict:
    return {
        "sighting_id": s.sighting_id,
        "plate_no": s.plate_no,
        "plate_conf": s.plate_conf,
        "outcome": s.outcome,
        "reason_codes": s.reason_codes,
        "vehicle_type": s.vehicle_type,
        "colour_family": s.colour_family,
        "observed_at": s.observed_at,
        "total_ms": s.total_ms,
        "camera": {
            "id": camera.camera_id,
            "name": camera.name,
            "lat": camera.lat,
            "lon": camera.lon,
        },
        "evidence": evidence,
    }


@router.get("/sightings", tags=["sightings"])
def list_sightings(
    plate: str | None = Query(None, max_length=15),
    camera_id: str | None = Query(None, max_length=32),
    outcome: SightingOutcome | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    _: User = Depends(require(Action.VIEW_SIGHTINGS)),
    session: Session = Depends(get_session),
) -> list[dict]:
    """Recent sightings with outcome and camera (live monitor, plate search)."""
    stmt = (
        select(Sighting, Camera)
        .join(Camera, Camera.camera_id == Sighting.camera_id)
        .order_by(Sighting.observed_at.desc())
        .limit(limit)
    )
    if plate:
        stmt = stmt.where(Sighting.plate_no.like(f"{plate.strip().upper()}%"))
    if camera_id:
        stmt = stmt.where(Sighting.camera_id == camera_id)
    if outcome:
        stmt = stmt.where(Sighting.outcome == outcome)
    if since:
        stmt = stmt.where(Sighting.observed_at >= since)
    if until:
        stmt = stmt.where(Sighting.observed_at <= until)
    rows = session.execute(stmt).all()
    evidence = _evidence_by_sighting(session, [s.sighting_id for s, _ in rows])
    return [_sighting_row(s, c, evidence[s.sighting_id]) for s, c in rows]


@router.get("/plates/{plate_no}/timeline", tags=["sightings"])
def plate_timeline(
    plate_no: str,
    user: User = Depends(require(Action.VIEW_SIGHTINGS)),
    session: Session = Depends(get_session),
) -> dict:
    """Every sighting of one plate across all cameras, oldest first (FR-DSH-05)."""
    plate = plate_no.strip().upper()
    if not plate.isalnum() or not 4 <= len(plate) <= 15:
        raise HTTPException(422, "Not a valid plate number")
    rows = session.execute(
        select(Sighting, Camera)
        .join(Camera, Camera.camera_id == Sighting.camera_id)
        .where(Sighting.plate_no == plate)
        .order_by(Sighting.observed_at)
    ).all()
    evidence = _evidence_by_sighting(session, [s.sighting_id for s, _ in rows])
    vehicle = session.get(Vehicle, plate)
    result = {
        "plate_no": plate,
        "registry": (
            {
                "vehicle_type": vehicle.vehicle_type, "colour_family": vehicle.colour_family,
                "make": vehicle.make, "model": vehicle.model, "owner_name": vehicle.owner_name,
            }
            if vehicle
            else None
        ),
        "sightings": [_sighting_row(s, c, evidence[s.sighting_id]) for s, c in rows],
        "alerts": [],
        "reports": [],
    }  # fmt: skip
    if can(user.role, Action.VIEW_ALERTS):
        result["alerts"] = [
            {"alert_id": a.alert_id, "alert_type": a.alert_type, "severity": a.severity,
             "status": a.status, "created_at": a.created_at}
            for a in session.scalars(
                select(Alert).where(Alert.plate_no == plate).order_by(Alert.created_at)
            )
        ]  # fmt: skip
    if can(user.role, Action.VIEW_REPORTS):
        result["reports"] = [
            {"report_id": r.report_id, "report_type": r.report_type, "fir_ref": r.fir_ref,
             "recovery_status": r.recovery_status, "reported_at": r.reported_at}
            for r in session.scalars(
                select(VehicleReport).where(VehicleReport.plate_no == plate)
            )
        ]  # fmt: skip
    return result


def _camera_state(camera: Camera, now: datetime) -> str:
    """ONLINE only while frames keep arriving (FR-CAP-07)."""
    if camera.status != CameraStatus.ONLINE or camera.last_frame_at is None:
        return str(camera.status)
    return "ONLINE" if now - camera.last_frame_at <= STALE_AFTER else "OFFLINE"


@router.get("/cameras", tags=["cameras"])
def list_cameras(
    _: User = Depends(require(Action.VIEW_SIGHTINGS)),
    session: Session = Depends(get_session),
) -> list[dict]:
    now = datetime.now(UTC)
    rows = session.execute(
        select(Camera, PoliceStation.name)
        .join(PoliceStation, PoliceStation.station_id == Camera.station_id)
        .order_by(Camera.camera_id)
    ).all()
    return [
        {"camera_id": c.camera_id, "name": c.name, "lat": c.lat, "lon": c.lon,
         "station": station, "station_id": c.station_id, "source_type": c.source_type, "state": _camera_state(c, now),
         "last_frame_at": c.last_frame_at}
        for c, station in rows
    ]  # fmt: skip


@router.get("/system/health", tags=["system"])
def system_health(
    _: User = Depends(require(Action.VIEW_SIGHTINGS)),
    session: Session = Depends(get_session),
) -> dict:
    """The health panel: cameras, alert delivery backlog, open work (architecture §16)."""
    now = datetime.now(UTC)
    cameras = session.scalars(select(Camera)).all()
    outbox = dict(
        session.execute(
            select(Outbox.status, func.count()).group_by(Outbox.status)
        ).all()
    )
    last = session.scalar(select(func.max(Sighting.observed_at)))
    return {
        "database": "ok",
        "alert_mode": get_settings().alert_mode,
        "cameras_online": sum(_camera_state(c, now) == "ONLINE" for c in cameras),
        "cameras_total": len(cameras),
        "outbox_waiting": sum(
            outbox.get(s, 0)
            for s in (OutboxStatus.QUEUED, OutboxStatus.SENDING, OutboxStatus.RETRYING)
        ),
        "outbox_failed": outbox.get(OutboxStatus.FAILED, 0),
        "open_alerts": session.scalar(
            select(func.count())
            .select_from(Alert)
            .where(Alert.status.in_(OPEN_ALERT_STATUSES))
        ),
        "open_cases": session.scalar(
            select(func.count())
            .select_from(VehicleReport)
            .where(VehicleReport.recovery_status.in_(ACTIVE_RECOVERY_STATUSES))
        ),
        "last_sighting_at": last,
    }


@router.get("/evidence/{evidence_id}/image", tags=["evidence"])
def evidence_image(
    evidence_id: str,
    _: User = Depends(require(Action.VIEW_ALERTS)),
    session: Session = Depends(get_session),
) -> FileResponse:
    """An evidence image, only for signed-in users who may see alerts (NFR-SEC-03)."""
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(404, "Evidence not found")
    if evidence.purged_at is not None:
        raise HTTPException(410, "This evidence was removed by the retention policy")
    file = _file_for(evidence.path).resolve()
    allowed = Path(evidence_module.EVIDENCE_DIR).resolve()
    if not file.is_relative_to(allowed) or not file.is_file():
        raise HTTPException(404, "Evidence file is not available")
    return FileResponse(file, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})  # fmt: skip
