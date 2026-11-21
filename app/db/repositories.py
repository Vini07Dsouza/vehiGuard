"""Read and write records (task 1.2). Callers own the session and commit it.

Example:
    with SessionLocal() as session:
        vehicles = VehicleRepository(session)
        car = vehicles.get("KA19AB1234")
        session.commit()
"""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.db.models import (
    Base,
    Camera,
    PoliceStation,
    StatusHistory,
    User,
    Vehicle,
    VehicleReport,
)
from app.domain.states import (
    ACTIVE_RECOVERY_STATUSES,
    RECOVERY_TRANSITIONS,
    CameraStatus,
    HistoryEntity,
    RecoveryStatus,
    Role,
)
from app.services.audit import append_audit

M = TypeVar("M", bound=Base)


class Repository(Generic[M]):
    """Basic create, read, update and delete for one table."""

    model: type[M]

    def __init__(self, session: Session):
        self.session = session

    def get(self, key: Any) -> M | None:
        return self.session.get(self.model, key)

    def list(self, limit: int = 100, offset: int = 0) -> Sequence[M]:
        pk = self.model.__mapper__.primary_key[0]
        stmt = select(self.model).order_by(pk).limit(limit).offset(offset)
        return self.session.scalars(stmt).all()

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(self.model))

    def add(self, obj: M) -> M:
        self.session.add(obj)
        self.session.flush()
        return obj

    def update(self, obj: M, **fields: Any) -> M:
        for name, value in fields.items():
            if not hasattr(obj, name):
                raise AttributeError(f"{self.model.__name__} has no field {name!r}")
            setattr(obj, name, value)
        self.session.flush()
        return obj

    def delete(self, obj: M) -> None:
        self.session.delete(obj)
        self.session.flush()


class VehicleRepository(Repository[Vehicle]):
    model = Vehicle


class PoliceStationRepository(Repository[PoliceStation]):
    model = PoliceStation


class CameraRepository(Repository[Camera]):
    model = Camera

    def for_station(self, station_id: str) -> Sequence[Camera]:
        stmt = select(Camera).where(Camera.station_id == station_id)
        return self.session.scalars(stmt).all()

    def set_status(self, camera: Camera, status: CameraStatus) -> Camera:
        return self.update(camera, status=status)


class UserRepository(Repository[User]):
    model = User

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalar(select(User).where(User.username == username))

    def create(self, username: str, password: str, role: Role) -> User:
        user = User(username=username, password_hash=hash_password(password), role=role)
        return self.add(user)

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.get_by_username(username)
        if user and user.is_active and verify_password(password, user.password_hash):
            return user
        return None


class VehicleReportRepository(Repository[VehicleReport]):
    model = VehicleReport

    def active_for_plate(self, plate_no: str) -> Sequence[VehicleReport]:
        """Reports that sightings must be matched against (FR-REG-03)."""
        stmt = select(VehicleReport).where(
            VehicleReport.plate_no == plate_no,
            VehicleReport.recovery_status.in_(ACTIVE_RECOVERY_STATUSES),
        )
        return self.session.scalars(stmt).all()

    def all_active_plates(self) -> set[str]:
        stmt = select(VehicleReport.plate_no).where(
            VehicleReport.recovery_status.in_(ACTIVE_RECOVERY_STATUSES)
        )
        return set(self.session.scalars(stmt))

    def change_status(
        self,
        report: VehicleReport,
        new_status: RecoveryStatus,
        user_id: str | None,
        note: str | None = None,
        location: str | None = None,
    ) -> VehicleReport:
        """Move a report to a new recovery status, following architecture §6.3.

        Records a status_history row and an audit entry.
        """
        old = report.recovery_status
        if new_status not in RECOVERY_TRANSITIONS[old]:
            raise ValueError(f"Cannot change report from {old} to {new_status}")
        self.update(report, recovery_status=new_status)
        self.session.add(
            StatusHistory(
                entity_type=HistoryEntity.REPORT,
                entity_id=report.report_id,
                from_status=old,
                to_status=new_status,
                user_id=user_id,
                note=note,
                location=location,
            )
        )
        append_audit(
            self.session,
            action="REPORT_STATUS_CHANGED",
            entity="vehicle_reports",
            entity_id=report.report_id,
            details={"from": old, "to": new_status, "note": note, "location": location},
            user_id=user_id,
        )
        return report
