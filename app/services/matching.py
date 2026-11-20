"""Registry lookup and stolen/missing matching (tasks 3.1 and 3.8)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import load_yaml
from app.db.models import Vehicle, VehicleReport
from app.domain.decision_engine import ReportMatch
from app.domain.fuzzy import near_misses
from app.domain.states import ACTIVE_RECOVERY_STATUSES


@dataclass(frozen=True)
class RegistryMatch:
    vehicle: Vehicle | None  # FR-REG-01: the record, or None if not found
    reports: tuple[ReportMatch, ...]  # active reports for this exact plate
    possible_match_plates: tuple[str, ...]  # active report plates 1 edit away


def match_plate(session: Session, plate: str) -> RegistryMatch:
    max_distance = load_yaml("settings.yaml")["matching"]["fuzzy_max_edit_distance"]
    active = session.execute(
        select(
            VehicleReport.report_id,
            VehicleReport.plate_no,
            VehicleReport.report_type,
            VehicleReport.recovery_status,
        ).where(VehicleReport.recovery_status.in_(ACTIVE_RECOVERY_STATUSES))
    ).all()
    exact = tuple(
        ReportMatch(r.report_id, r.report_type, r.recovery_status)
        for r in active
        if r.plate_no == plate
    )
    return RegistryMatch(
        vehicle=session.get(Vehicle, plate),
        reports=exact,
        possible_match_plates=tuple(
            near_misses(plate, (r.plate_no for r in active), max_distance)
        ),
    )
