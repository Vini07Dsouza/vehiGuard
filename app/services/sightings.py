"""Turn a finished plate read into a stored sighting with evidence."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
from sqlalchemy.orm import Session

from app.db.models import Sighting, Vehicle
from app.domain.states import ColourFamily, EvidenceKind, SightingOutcome, VehicleType
from app.pipeline.plate_validator import VoteStatus
from app.services.evidence import save_evidence


@dataclass
class PlateEvent:
    """Everything the pipeline knows when it finishes with one vehicle."""

    camera_id: str
    status: VoteStatus  # ACCEPTED, NO_PLATE or LOW_CONFIDENCE
    observed_at: float  # server timestamp (seconds since epoch)
    plate: str | None = None
    confidence: float | None = None
    vehicle_type: VehicleType = VehicleType.UNKNOWN
    colour_family: ColourFamily = ColourFamily.UNKNOWN  # Phase 5
    vehicle_image: np.ndarray | None = None
    plate_image: np.ndarray | None = None
    stage_ms: dict = field(default_factory=dict)


def registry_outcome(session: Session, event: PlateEvent) -> SightingOutcome:
    """Phase 2 stand-in for the decision engine (Phase 3 replaces this).

    PRD §5 rows 1, 7 and 8 only: no plate, registered (PASS), unknown plate.
    """
    if event.status == VoteStatus.NO_PLATE:
        return SightingOutcome.NO_PLATE
    if event.status == VoteStatus.LOW_CONFIDENCE:
        return SightingOutcome.LOW_CONFIDENCE
    if session.get(Vehicle, event.plate) is None:
        return SightingOutcome.UNKNOWN_PLATE
    return SightingOutcome.PASS


Decide = Callable[[Session, PlateEvent], SightingOutcome]


def record_sighting(
    session: Session, event: PlateEvent, decide: Decide = registry_outcome
) -> Sighting:
    """Store the sighting and its evidence images. The caller commits."""
    observed_at = datetime.fromtimestamp(event.observed_at, UTC)
    sighting = Sighting(
        camera_id=event.camera_id,
        plate_no=event.plate,
        plate_conf=event.confidence,
        vehicle_type=event.vehicle_type,
        colour_family=event.colour_family,
        observed_at=observed_at,
        outcome=decide(session, event),
        reason_codes=[],
        stage_ms=event.stage_ms,
        total_ms=event.stage_ms.get("total"),
    )
    session.add(sighting)
    session.flush()  # creates sighting_id for the evidence file names
    for kind, image in (
        (EvidenceKind.VEHICLE_FRAME, event.vehicle_image),
        (EvidenceKind.PLATE_CROP, event.plate_image),
    ):
        if image is not None and image.size:
            save_evidence(session, sighting.sighting_id, kind, image, observed_at)
    return sighting
