"""VehiGuard database tables (architecture §7.1).

Change these, then create a migration:
    alembic revision --autogenerate -m "describe the change"
    alembic upgrade head

Note: for a NEW table with enum columns, autogenerate also writes extra
sa.CheckConstraint(...) lines. Delete them from the migration; the enum
column already creates its CHECK constraint (otherwise PostgreSQL reports
"check constraint ... already exists").
"""

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.states import (
    AlertStatus,
    AlertType,
    CameraSourceType,
    CameraStatus,
    ColourFamily,
    EvidenceKind,
    HistoryEntity,
    OutboxChannel,
    OutboxStatus,
    RecoveryStatus,
    ReportType,
    Role,
    Severity,
    SightingOutcome,
    VehicleType,
)

# Predictable constraint names, so Alembic migrations stay stable
NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def new_id() -> str:
    return uuid4().hex


def enum_col(enum_cls: type[StrEnum]) -> SAEnum:
    """Store an enum as plain text with a CHECK constraint (easy to migrate)."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        name=enum_cls.__name__.lower(),
        values_callable=lambda e: [m.value for m in e],
    )


def created_at_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_col(Role))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = created_at_col()


class PoliceStation(Base):
    __tablename__ = "police_stations"
    station_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    email: Mapped[str] = mapped_column(String(255))


class Camera(Base):
    __tablename__ = "cameras"
    camera_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("police_stations.station_id"))
    name: Mapped[str] = mapped_column(String(100))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    source_type: Mapped[CameraSourceType] = mapped_column(enum_col(CameraSourceType))
    source_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[CameraStatus] = mapped_column(
        enum_col(CameraStatus), default=CameraStatus.STOPPED
    )
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Vehicle(Base):
    """Dummy registry record. Owners are fictional."""

    __tablename__ = "vehicles"
    plate_no: Mapped[str] = mapped_column(String(15), primary_key=True)
    vehicle_type: Mapped[VehicleType] = mapped_column(enum_col(VehicleType))
    make: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    colour_family: Mapped[ColourFamily] = mapped_column(enum_col(ColourFamily))
    owner_name: Mapped[str] = mapped_column(String(100))


class VehicleReport(Base):
    """Stolen or missing report (fictional FIR reference)."""

    __tablename__ = "vehicle_reports"
    __table_args__ = (Index("ix_vehicle_reports_plate_status", "plate_no", "recovery_status"),)  # fmt: skip
    report_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    plate_no: Mapped[str] = mapped_column(ForeignKey("vehicles.plate_no"))
    report_type: Mapped[ReportType] = mapped_column(enum_col(ReportType))
    fir_ref: Mapped[str] = mapped_column(String(50))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reported_place: Mapped[str] = mapped_column(String(200))
    recovery_status: Mapped[RecoveryStatus] = mapped_column(
        enum_col(RecoveryStatus), default=RecoveryStatus.REPORTED
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Sighting(Base):
    """One accepted (or rejected) plate observation at a camera.

    plate_no has no foreign key: unknown plates must be stored too.
    """

    __tablename__ = "sightings"
    __table_args__ = (Index("ix_sightings_plate_observed", "plate_no", "observed_at"),)
    sighting_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=new_id
    )
    camera_id: Mapped[str] = mapped_column(ForeignKey("cameras.camera_id"))
    plate_no: Mapped[str | None] = mapped_column(String(15))
    plate_conf: Mapped[float | None] = mapped_column(Float)
    vehicle_type: Mapped[VehicleType] = mapped_column(
        enum_col(VehicleType), default=VehicleType.UNKNOWN
    )
    colour_family: Mapped[ColourFamily] = mapped_column(
        enum_col(ColourFamily), default=ColourFamily.UNKNOWN
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[SightingOutcome] = mapped_column(enum_col(SightingOutcome))
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    stage_ms: Mapped[dict] = mapped_column(JSON, default=dict)  # per-stage timings
    total_ms: Mapped[float | None] = mapped_column(Float)


class Evidence(Base):
    __tablename__ = "evidence"
    evidence_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=new_id
    )
    sighting_id: Mapped[str] = mapped_column(
        ForeignKey("sightings.sighting_id"), index=True
    )
    kind: Mapped[EvidenceKind] = mapped_column(enum_col(EvidenceKind))
    path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    purge_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        # de-duplication key (architecture §8.5)
        Index("ix_alerts_plate_type_status", "plate_no", "alert_type", "status"),
    )
    alert_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    alert_type: Mapped[AlertType] = mapped_column(enum_col(AlertType))
    severity: Mapped[Severity] = mapped_column(enum_col(Severity))
    plate_no: Mapped[str] = mapped_column(String(15))
    sighting_id: Mapped[str] = mapped_column(ForeignKey("sightings.sighting_id"))
    related_sighting_id: Mapped[str | None] = mapped_column(
        ForeignKey("sightings.sighting_id")
    )
    report_id: Mapped[str | None] = mapped_column(
        ForeignKey("vehicle_reports.report_id")
    )
    station_id: Mapped[str] = mapped_column(ForeignKey("police_stations.station_id"))
    status: Mapped[AlertStatus] = mapped_column(
        enum_col(AlertStatus), default=AlertStatus.NEW
    )
    reason_codes: Mapped[list] = mapped_column(JSON, default=list)
    journey_json: Mapped[dict | None] = mapped_column(JSON)
    merged_count: Mapped[int] = mapped_column(Integer, default=1)
    # later sightings merged into this alert (de-duplication, FR-ALR-05)
    merged_sighting_ids: Mapped[list] = mapped_column(
        JSON, default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = created_at_col()


class StatusHistory(Base):
    """Append-only record of every alert or report status change."""

    __tablename__ = "status_history"
    __table_args__ = (Index("ix_status_history_entity", "entity_type", "entity_id"),)
    history_id: Mapped[str] = mapped_column(
        String(32), primary_key=True, default=new_id
    )
    entity_type: Mapped[HistoryEntity] = mapped_column(enum_col(HistoryEntity))
    entity_id: Mapped[str] = mapped_column(String(32))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    note: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = created_at_col()


class Outbox(Base):
    """Alert deliveries waiting to be sent or retried."""

    __tablename__ = "outbox"
    __table_args__ = (Index("ix_outbox_status_next", "status", "next_attempt_at"),)
    outbox_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.alert_id"))
    channel: Mapped[OutboxChannel] = mapped_column(enum_col(OutboxChannel))
    target: Mapped[str] = mapped_column(String(255))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[OutboxStatus] = mapped_column(
        enum_col(OutboxStatus), default=OutboxStatus.QUEUED
    )
    last_error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """Append-only audit trail with a hash chain: hash = H(prev_hash + record)."""

    __tablename__ = "audit_log"
    log_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    seq: Mapped[int] = mapped_column(Integer, Identity(), unique=True)  # chain order
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    action: Mapped[str] = mapped_column(String(50))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(32))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    ts: Mapped[datetime] = created_at_col()
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
