"""Database tables for VehiLence (see docs/architecture.md, section 7)."""

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ---------- Reference data (dummy records you create) ----------


class Owner(Base):
    __tablename__ = "owners"
    owner_id: Mapped[str] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    phone: Mapped[str | None]
    email: Mapped[str | None]
    telegram_chat_id: Mapped[str | None]
    consent_ref: Mapped[str | None]  # volunteer code, e.g. V01


class OwnerFace(Base):
    __tablename__ = "owner_faces"
    face_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.owner_id"))
    embedding: Mapped[bytes]  # float32 vector stored as bytes
    image_path: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Vehicle(Base):
    __tablename__ = "vehicles"
    plate_no: Mapped[str] = mapped_column(primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("owners.owner_id"))
    registration_type: Mapped[str]  # PERMANENT / TEMPORARY / TRADE
    valid_until: Mapped[date | None]  # used for temporary registrations
    status: Mapped[str] = mapped_column(default="ACTIVE")
    # ACTIVE / STOLEN / MISSING / BLACKLISTED
    make: Mapped[str | None]
    model: Mapped[str | None]
    colour: Mapped[str | None]


class WantedPerson(Base):
    __tablename__ = "wanted_list"
    wanted_id: Mapped[str] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    case_ref: Mapped[str | None]
    severity: Mapped[str | None]
    embedding: Mapped[bytes]
    image_path: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="ACTIVE")


class MissingReport(Base):
    __tablename__ = "missing_reports"
    report_id: Mapped[str] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    report_ref: Mapped[str | None]
    embedding: Mapped[bytes]
    image_path: Mapped[str | None]
    status: Mapped[str] = mapped_column(default="ACTIVE")


class PoliceStation(Base):
    __tablename__ = "police_stations"
    station_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    lat: Mapped[float]
    lon: Mapped[float]
    email: Mapped[str | None]
    phone: Mapped[str | None]


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    checkpoint_id: Mapped[str] = mapped_column(primary_key=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("police_stations.station_id"))
    name: Mapped[str]
    lat: Mapped[float]
    lon: Mapped[float]


# ---------- Runtime data (created while the system runs) ----------


class DetectionSession(Base):
    __tablename__ = "sessions"
    session_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    checkpoint_id: Mapped[str | None] = mapped_column(
        ForeignKey("checkpoints.checkpoint_id")
    )
    plate_no: Mapped[str | None]
    plate_conf: Mapped[float | None]
    registry_status: Mapped[str | None]
    face_result: Mapped[str | None]  # MATCH / MISMATCH / UNVERIFIABLE
    face_score: Mapped[float | None]
    outcome: Mapped[str | None]
    reason_codes: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(default=utcnow)
    ended_at: Mapped[datetime | None]


class Evidence(Base):
    __tablename__ = "evidence"
    evidence_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"))
    kind: Mapped[str]  # PLATE_CROP / VEHICLE_FRAME / DRIVER_FACE
    path: Mapped[str]
    purge_after: Mapped[datetime | None]


class ReviewCase(Base):
    __tablename__ = "review_cases"
    case_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"))
    reason: Mapped[str]  # WANTED_MATCH, NO_PLATE, FACE_UNVERIFIABLE, ...
    candidate_type: Mapped[str | None]  # WANTED / MISSING
    candidate_id: Mapped[str | None]
    score: Mapped[float | None]
    status: Mapped[str] = mapped_column(default="PENDING")
    decided_by: Mapped[str | None]
    decided_at: Mapped[datetime | None]
    note: Mapped[str | None] = mapped_column(Text)


class OwnerConfirmation(Base):
    __tablename__ = "owner_confirmations"
    conf_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"))
    owner_id: Mapped[str] = mapped_column(ForeignKey("owners.owner_id"))
    token_hash: Mapped[str | None]
    sent_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    response: Mapped[str | None]  # ALLOW / COMPLAIN
    responded_at: Mapped[datetime | None]


class Alert(Base):
    __tablename__ = "alerts"
    alert_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.session_id"))
    station_id: Mapped[str | None] = mapped_column(
        ForeignKey("police_stations.station_id")
    )
    type: Mapped[str]
    severity: Mapped[str]
    payload_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(default="QUEUED")
    merged_count: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class OutboxItem(Base):
    __tablename__ = "outbox"
    outbox_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.alert_id"))
    channel: Mapped[str]  # SIMULATED / SMTP / TELEGRAM / TWILIO
    target: Mapped[str]
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(default="QUEUED")


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(unique=True)
    password_hash: Mapped[str]
    role: Mapped[str]  # ADMIN / POLICE_OP / CHECKPOINT_OP / VIEWER


class AuditLog(Base):
    __tablename__ = "audit_log"
    log_id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.user_id"))
    action: Mapped[str]
    entity: Mapped[str | None]
    entity_id: Mapped[str | None]
    details: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(default=utcnow)
    prev_hash: Mapped[str | None]
    hash: Mapped[str | None]
