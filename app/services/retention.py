"""Evidence retention (task 6.5, FR-EVD-03, FR-ADM-04).

Evidence older than EVIDENCE_RETENTION_DAYS (its purge_after date) is deleted
from disk, EXCEPT evidence that is still needed:
  - the sighting is on an open alert (this one, the earlier one of a suspected
    clone, or one merged into it), or
  - the sighting's plate has an open stolen/missing report (an open case).

A purged row is kept with purged_at set and its SHA-256, so the record shows
the evidence existed and was removed by policy, not lost. Each run is audited.

Run on its own:  python -m app.services.retention [--dry-run]
"""

import argparse
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR
from app.db.models import Alert, Evidence, Sighting, VehicleReport
from app.domain.states import ACTIVE_RECOVERY_STATUSES, OPEN_ALERT_STATUSES
from app.services.audit import append_audit

log = logging.getLogger("vehiguard.retention")


def protected_sighting_ids(session: Session) -> set[str]:
    """Sightings whose evidence must be kept: on an open alert."""
    keep: set[str] = set()
    for alert in session.scalars(
        select(Alert).where(Alert.status.in_(OPEN_ALERT_STATUSES))
    ):
        keep.add(alert.sighting_id)
        if alert.related_sighting_id:
            keep.add(alert.related_sighting_id)
        keep.update(alert.merged_sighting_ids or [])
    return keep


def _file_for(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT_DIR / p


def purge_expired(
    session: Session,
    now: datetime | None = None,
    dry_run: bool = False,
    user_id: str | None = None,
) -> dict[str, int]:
    """Delete expired, unneeded evidence. The caller commits."""
    now = now or datetime.now(UTC)
    on_open_alert = protected_sighting_ids(session)
    open_case_plates = set(
        session.scalars(
            select(VehicleReport.plate_no).where(
                VehicleReport.recovery_status.in_(ACTIVE_RECOVERY_STATUSES)
            )
        )
    )
    result = {"purged": 0, "kept_open_alert": 0, "kept_open_case": 0, "missing_file": 0}
    expired = session.execute(
        select(Evidence, Sighting.plate_no)
        .join(Sighting, Sighting.sighting_id == Evidence.sighting_id)
        .where(Evidence.purge_after < now, Evidence.purged_at.is_(None))
    ).all()
    for evidence, plate in expired:
        if evidence.sighting_id in on_open_alert:
            result["kept_open_alert"] += 1
            continue
        if plate in open_case_plates:
            result["kept_open_case"] += 1
            continue
        if not dry_run:
            file = _file_for(evidence.path)
            if file.exists():
                file.unlink()
            else:
                result["missing_file"] += 1  # already gone; still mark it purged
            evidence.purged_at = now
        result["purged"] += 1
    if not dry_run:
        append_audit(
            session, "EVIDENCE_PURGED", "evidence", details=result, user_id=user_id
        )
        session.flush()
    return result


def main() -> None:
    from app.db.session import SessionLocal

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="count, delete nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with SessionLocal() as session:
        result = purge_expired(session, dry_run=args.dry_run)
        session.commit()
    print(("Would purge" if args.dry_run else "Purged"), result)


if __name__ == "__main__":
    main()
