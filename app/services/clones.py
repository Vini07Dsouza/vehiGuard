"""Clone analysis against stored sightings (tasks 4.3 and 4.1).

find_clone_signal: loads the plate's earlier sightings at OTHER cameras inside
CLONE_WINDOW_H and applies the impossible-journey rule. Only reliable reads
take part (FR-CLN-07, PRD §5 safety rule 1).

recent_duplicate: the same plate at the same camera within
SIGHTING_COOLDOWN_S is the same visit (FR-SIG-02), not a new sighting.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import load_yaml
from app.db.models import Camera, Sighting
from app.domain.clone_analyser import CloneConfig, CloneResult, SightingPoint, analyse
from app.domain.states import SightingOutcome

# Outcomes that never feed clone analysis
UNRELIABLE = (
    SightingOutcome.NO_PLATE,
    SightingOutcome.LOW_CONFIDENCE,
    SightingOutcome.POSSIBLE_MATCH,
    SightingOutcome.ERROR,
)


def clone_config() -> CloneConfig:
    return CloneConfig.from_settings(load_yaml("settings.yaml")["clone_detection"])


def find_clone_signal(
    session: Session,
    plate: str,
    camera_id: str,
    observed_at: datetime,
    cfg: CloneConfig | None = None,
) -> CloneResult:
    cfg = cfg or clone_config()
    camera = session.get(Camera, camera_id)
    rows = session.execute(
        select(
            Sighting.sighting_id,
            Sighting.camera_id,
            Sighting.observed_at,
            Camera.lat,
            Camera.lon,
        )
        .join(Camera, Camera.camera_id == Sighting.camera_id)
        .where(
            Sighting.plate_no == plate,
            Sighting.camera_id != camera_id,
            Sighting.observed_at <= observed_at,
            Sighting.observed_at >= observed_at - timedelta(hours=cfg.window_h),
            Sighting.outcome.not_in(UNRELIABLE),
        )
    ).all()
    earlier = [
        SightingPoint(r.sighting_id, r.camera_id, r.lat, r.lon, r.observed_at)
        for r in rows
    ]
    new = SightingPoint("new", camera_id, camera.lat, camera.lon, observed_at)
    return analyse(new, earlier, cfg)


def recent_duplicate(
    session: Session, plate: str, camera_id: str, observed_at: datetime
) -> Sighting | None:
    """An existing sighting of this plate at this camera within the cooldown."""
    cooldown = load_yaml("settings.yaml")["sightings"]["sighting_cooldown_s"]
    return session.scalar(
        select(Sighting)
        .where(
            Sighting.plate_no == plate,
            Sighting.camera_id == camera_id,
            Sighting.observed_at >= observed_at - timedelta(seconds=cooldown),
            Sighting.observed_at <= observed_at,
        )
        .order_by(Sighting.observed_at.desc())
        .limit(1)
    )
