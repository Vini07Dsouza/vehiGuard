"""Turn a finished plate read into a sighting, a decision and alerts (task 3.7).

event -> registry match -> decision engine -> sighting + evidence -> alerts
"""

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import load_yaml
from app.db.models import Alert, Evidence, Sighting, Vehicle
from app.domain.appearance import Appearance, compare
from app.domain.clone_analyser import CloneResult
from app.domain.decision_engine import Decision, DecisionInput, decide
from app.domain.states import ColourFamily, EvidenceKind, VehicleType
from app.pipeline.plate_validator import VoteStatus
from app.services.alerts import apply_decision
from app.services.clones import find_clone_signal, recent_duplicate
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
    decision: Decision | None  # None for a duplicate (same visit)
    alerts: list[Alert]
    duplicate: bool = False  # merged into a recent sighting (FR-SIG-02)
    clone: CloneResult | None = None


def decision_input(
    session: Session, event: PlateEvent, observed_at: datetime
) -> tuple[DecisionInput, CloneResult | None]:
    """Collect the facts the decision engine needs: registry, reports, clones."""
    if event.status != VoteStatus.ACCEPTED or not event.plate:
        return DecisionInput(read_status=str(event.status)), None
    match = match_plate(session, event.plate)
    clone = None
    # Safety rule 1: a near-miss of a stolen plate never feeds clone analysis
    if match.reports or not match.possible_match_plates:
        clone = find_clone_signal(session, event.plate, event.camera_id, observed_at)
    observed = Appearance(event.vehicle_type, event.colour_family)
    return (
        DecisionInput(
            read_status="ACCEPTED",
            plate=event.plate,
            registered=match.vehicle is not None,
            reports=match.reports,
            possible_match_plates=match.possible_match_plates,
            impossible_journey=bool(clone and clone.impossible_journey),
            sighting_mismatch=_earlier_mismatch(session, observed, clone),  # AM
            registry_mismatch=_registry_mismatch(observed, match.vehicle),  # RM
            flag_unregistered=load_yaml("settings.yaml")["matching"][
                "flag_unregistered"
            ],
        ),
        clone,
    )


def _registry_mismatch(observed: Appearance, vehicle: Vehicle | None) -> bool:
    """RM: the vehicle looks different from its registry record (FR-APP-03)."""
    if vehicle is None:
        return False
    return compare(
        observed, Appearance(vehicle.vehicle_type, vehicle.colour_family)
    ).mismatch


def _earlier_mismatch(
    session: Session, observed: Appearance, clone: CloneResult | None
) -> bool:
    """AM: the vehicle looks different from the plate's earlier sighting (FR-APP-04).

    The earlier sighting is the one on the impossible journey, otherwise the
    most recent one at another camera inside the clone window.
    """
    if clone is None:
        return False
    earlier_id = (
        clone.journey.from_sighting
        if clone.journey
        else (clone.checked[0].from_sighting if clone.checked else None)
    )
    if earlier_id is None:
        return False
    earlier = session.get(Sighting, earlier_id)
    return compare(observed, Appearance(earlier.vehicle_type, earlier.colour_family)).mismatch  # fmt: skip


def _save_images(session: Session, sighting: Sighting, event: PlateEvent) -> None:
    for kind, image in (
        (EvidenceKind.VEHICLE_FRAME, event.vehicle_image),
        (EvidenceKind.PLATE_CROP, event.plate_image),
    ):
        if image is not None and image.size:
            save_evidence(
                session, sighting.sighting_id, kind, image, sighting.observed_at
            )


def _merge_duplicate(session: Session, existing: Sighting, event: PlateEvent) -> None:
    """Same visit: keep the better-quality frame (higher OCR confidence)."""
    if (event.confidence or 0) <= (existing.plate_conf or 0):
        return
    existing.plate_conf = event.confidence
    for old in session.scalars(
        select(Evidence).where(Evidence.sighting_id == existing.sighting_id)
    ):
        session.delete(old)
    session.flush()
    _save_images(session, existing, event)  # overwrites the same file names


def record_sighting(session: Session, event: PlateEvent) -> SightingResult:
    """Decide, then store the sighting, its evidence and any alerts.

    The caller commits (one transaction: all of it is stored, or none).
    """
    t0 = time.perf_counter()
    observed_at = datetime.fromtimestamp(event.observed_at, UTC)
    if event.status == VoteStatus.ACCEPTED and event.plate:
        existing = recent_duplicate(session, event.plate, event.camera_id, observed_at)
        if existing:
            _merge_duplicate(session, existing, event)
            return SightingResult(existing, None, [], duplicate=True)

    given, clone = decision_input(session, event, observed_at)
    decision = decide(given)
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
    _save_images(session, sighting, event)
    alerts = apply_decision(session, decision, sighting, observed_at, clone)
    return SightingResult(sighting, decision, alerts, clone=clone)
