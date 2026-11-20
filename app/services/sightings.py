"""Turn a finished plate read into a sighting, a decision and alerts (task 3.7).

event -> registry match -> decision engine -> sighting + evidence -> alerts
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
from sqlalchemy.orm import Session

from app.core.config import load_yaml
from app.db.models import Alert, Sighting
from app.domain.decision_engine import Decision, DecisionInput, decide
from app.domain.states import ColourFamily, EvidenceKind, VehicleType
from app.pipeline.plate_validator import VoteStatus
from app.services.alerts import apply_decision
from app.services.evidence import save_evidence
from app.services.matching import match_plate


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


@dataclass
class SightingResult:
    sighting: Sighting
    decision: Decision
    alerts: list[Alert]


def decision_input(session: Session, event: PlateEvent) -> DecisionInput:
    """Collect the facts the decision engine needs (registry and reports)."""
    if event.status != VoteStatus.ACCEPTED or not event.plate:
        return DecisionInput(read_status=str(event.status))
    match = match_plate(session, event.plate)
    return DecisionInput(
        read_status="ACCEPTED",
        plate=event.plate,
        registered=match.vehicle is not None,
        reports=match.reports,
        possible_match_plates=match.possible_match_plates,
        # Clone (IJ) and appearance (AM, RM) signals arrive in Phases 4 and 5
        flag_unregistered=load_yaml("settings.yaml")["matching"]["flag_unregistered"],
    )


def record_sighting(session: Session, event: PlateEvent) -> SightingResult:
    """Decide, then store the sighting, its evidence and any alerts.

    The caller commits (one transaction: all of it is stored, or none).
    """
    t0 = time.perf_counter()
    decision = decide(decision_input(session, event))
    observed_at = datetime.fromtimestamp(event.observed_at, UTC)
    stage_ms = dict(event.stage_ms)
    stage_ms["decision"] = round((time.perf_counter() - t0) * 1000, 1)
    sighting = Sighting(
        camera_id=event.camera_id,
        plate_no=event.plate,
        plate_conf=event.confidence,
        vehicle_type=event.vehicle_type,
        colour_family=event.colour_family,
        observed_at=observed_at,
        outcome=decision.outcome,
        reason_codes=[str(r) for r in decision.reason_codes],
        stage_ms=stage_ms,
        total_ms=stage_ms.get("total"),
    )
    session.add(sighting)
    session.flush()  # creates sighting_id for the evidence file names
    for kind, image in (
        (EvidenceKind.VEHICLE_FRAME, event.vehicle_image),
        (EvidenceKind.PLATE_CROP, event.plate_image),
    ):
        if image is not None and image.size:
            save_evidence(session, sighting.sighting_id, kind, image, observed_at)
    alerts = apply_decision(session, decision, sighting, observed_at)
    return SightingResult(sighting, decision, alerts)
