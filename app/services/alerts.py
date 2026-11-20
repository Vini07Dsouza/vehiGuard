"""Create, merge and route alerts (tasks 3.4 and 3.5, FR-ALR-01..06).

The decision engine says WHICH alerts to raise; this module only stores them:
  - route each alert to the police station nearest the camera (FR-GEO-02)
  - merge a repeat of the same plate + alert type within ALERT_COOLDOWN_S
    into the open alert (merged_count + 1) instead of a new one (FR-ALR-05)
  - queue an email for HIGH and MEDIUM alerts in the outbox (FR-ALR-03/04)
  - move matching REPORTED reports to DETECTED (FR-CASE-02)
"""

import zlib
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings, load_yaml
from app.db.models import (
    Alert,
    Camera,
    Evidence,
    Outbox,
    PoliceStation,
    Sighting,
    Vehicle,
    VehicleReport,
)
from app.db.repositories import VehicleReportRepository
from app.domain.clone_analyser import CloneResult
from app.domain.decision_engine import AlertSpec, Decision
from app.domain.geo import nearest
from app.domain.states import AlertStatus, AlertType, OutboxChannel, RecoveryStatus
from app.services.audit import append_audit

OPEN_ALERT_STATUSES = (
    AlertStatus.NEW,
    AlertStatus.ACKNOWLEDGED,
    AlertStatus.UNDER_INVESTIGATION,
)
_station_cache: dict[str, tuple[str, float]] = {}


def station_for_camera(session: Session, camera: Camera) -> tuple[PoliceStation, float]:
    """Nearest police station to a camera and its distance in km (cached)."""
    cached = _station_cache.get(camera.camera_id)
    if cached:
        return session.get(PoliceStation, cached[0]), cached[1]
    station, km = nearest(
        camera.lat, camera.lon, session.scalars(select(PoliceStation)).all()
    )
    _station_cache[camera.camera_id] = (station.station_id, km)
    return station, km


def clear_station_cache() -> None:
    """Call after stations or camera locations change."""
    _station_cache.clear()


def _lock_key(plate: str, alert_type: str) -> int:
    # Same plate + type from two cameras at once must not create two alerts
    return zlib.crc32(f"{plate}|{alert_type}".encode()) & 0x7FFFFFFF


def _open_duplicate(session, plate, alert_type, now) -> Alert | None:
    cooldown = load_yaml("settings.yaml")["alerts"]["alert_cooldown_s"]
    return session.scalar(
        select(Alert)
        .where(
            Alert.plate_no == plate,
            Alert.alert_type == alert_type,
            Alert.status.in_(OPEN_ALERT_STATUSES),
            Alert.created_at >= now - timedelta(seconds=cooldown),
        )
        .order_by(Alert.created_at.desc())
        .limit(1)
    )


def _queue_email(session: Session, alert: Alert, station: PoliceStation) -> None:
    live = get_settings().alert_mode == "live"
    session.add(
        Outbox(
            alert_id=alert.alert_id,
            channel=OutboxChannel.EMAIL if live else OutboxChannel.SIMULATED,
            target=station.email,
        )
    )


def raise_alert(
    session: Session,
    spec: AlertSpec,
    sighting: Sighting,
    now: datetime,
    clone: CloneResult | None = None,
) -> tuple[Alert, bool]:
    """Store one alert from the engine. Returns (alert, created_new)."""
    if session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:k)"),
            {"k": _lock_key(sighting.plate_no, spec.alert_type)},
        )
    existing = _open_duplicate(session, sighting.plate_no, spec.alert_type, now)
    if existing:
        existing.merged_count += 1
        existing.merged_sighting_ids = [
            *existing.merged_sighting_ids,
            sighting.sighting_id,
        ]
        append_audit(
            session,
            "ALERT_MERGED",
            "alerts",
            existing.alert_id,
            {
                "sighting_id": sighting.sighting_id,
                "merged_count": existing.merged_count,
            },
        )
        return existing, False

    camera = session.get(Camera, sighting.camera_id)
    station, km = station_for_camera(session, camera)
    alert = Alert(
        alert_type=spec.alert_type,
        severity=spec.severity,
        plate_no=sighting.plate_no,
        sighting_id=sighting.sighting_id,
        report_id=spec.report_id,
        station_id=station.station_id,
        reason_codes=[str(r) for r in spec.reason_codes],
        created_at=now,
    )
    if spec.alert_type == AlertType.SUSPECTED_CLONE and clone and clone.journey:
        # FR-CLN-03/05: the journey, and a link to the earlier sighting's evidence
        alert.related_sighting_id = clone.journey.from_sighting
        alert.journey_json = clone.journey_json()
    session.add(alert)
    session.flush()
    if spec.email:
        _queue_email(session, alert, station)
    append_audit(
        session,
        "ALERT_CREATED",
        "alerts",
        alert.alert_id,
        {
            "type": spec.alert_type,
            "severity": spec.severity,
            "plate": sighting.plate_no,
            "station": station.station_id,
            "station_km": round(km, 2),
        },
    )
    return alert, True


def apply_decision(
    session: Session,
    decision: Decision,
    sighting: Sighting,
    now: datetime,
    clone: CloneResult | None = None,
) -> list[Alert]:
    """Store the alerts and report changes the engine asked for."""
    alerts = [
        raise_alert(session, spec, sighting, now, clone)[0] for spec in decision.alerts
    ]
    reports = VehicleReportRepository(session)
    for report_id in decision.reports_to_detect:
        report = session.get(VehicleReport, report_id)
        if report and report.recovery_status == RecoveryStatus.REPORTED:
            reports.change_status(
                report,
                RecoveryStatus.DETECTED,
                user_id=None,  # automatic (FR-CASE-02)
                note=f"Detected by camera {sighting.camera_id}",
            )
    return alerts


def alert_payload(session: Session, alert: Alert) -> dict:
    """Everything a police officer needs (FR-ALR-01)."""
    sighting = session.get(Sighting, alert.sighting_id)
    camera = session.get(Camera, sighting.camera_id)
    station = session.get(PoliceStation, alert.station_id)
    report = session.get(VehicleReport, alert.report_id) if alert.report_id else None
    evidence = session.scalars(
        select(Evidence).where(Evidence.sighting_id == sighting.sighting_id)
    ).all()
    return {
        "alert_id": alert.alert_id,
        "type": alert.alert_type,
        "severity": alert.severity,
        "plate": alert.plate_no,
        "observed_at": sighting.observed_at.isoformat(),
        "camera": {
            "id": camera.camera_id,
            "name": camera.name,
            "lat": camera.lat,
            "lon": camera.lon,
        },
        "station": {"id": station.station_id, "name": station.name},
        "reason_codes": alert.reason_codes,
        "scores": {"plate_confidence": sighting.plate_conf},
        "vehicle_type": sighting.vehicle_type,
        "colour_family": sighting.colour_family,
        "report": (
            {
                "id": report.report_id,
                "type": report.report_type,
                "fir_ref": report.fir_ref,
                "status": report.recovery_status,
            }
            if report
            else None
        ),
        "evidence": [
            {"kind": e.kind, "path": e.path, "sha256": e.sha256} for e in evidence
        ],
        "merged_count": alert.merged_count,
        "registry": _registry_summary(session, alert.plate_no),
        "journey": alert.journey_json,  # suspected clones only
        "earlier_sighting": _sighting_summary(session, alert.related_sighting_id),
    }


def _sighting_summary(session: Session, sighting_id: str | None) -> dict | None:
    """The earlier sighting of a suspected clone, with its evidence (FR-CLN-05)."""
    if not sighting_id:
        return None
    sighting = session.get(Sighting, sighting_id)
    camera = session.get(Camera, sighting.camera_id)
    evidence = session.scalars(
        select(Evidence).where(Evidence.sighting_id == sighting_id)
    ).all()
    return {
        "sighting_id": sighting_id,
        "observed_at": sighting.observed_at.isoformat(),
        "camera": {"id": camera.camera_id, "name": camera.name,
                   "lat": camera.lat, "lon": camera.lon},
        "vehicle_type": sighting.vehicle_type,
        "colour_family": sighting.colour_family,
        "evidence": [{"kind": e.kind, "path": e.path, "sha256": e.sha256} for e in evidence],
    }  # fmt: skip


def _registry_summary(session: Session, plate: str) -> dict | None:
    """What the registry says this vehicle looks like (for the RM comparison)."""
    vehicle = session.get(Vehicle, plate)
    if vehicle is None:
        return None
    return {
        "vehicle_type": vehicle.vehicle_type,
        "colour_family": vehicle.colour_family,
        "make": vehicle.make,
        "model": vehicle.model,
    }
