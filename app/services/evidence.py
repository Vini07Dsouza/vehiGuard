"""Save evidence images with a SHA-256 fingerprint (FR-PLT-09, FR-EVD-01/02)."""

import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import ROOT_DIR, load_yaml
from app.db.models import Evidence
from app.domain.states import EvidenceKind

EVIDENCE_DIR = ROOT_DIR / "data" / "evidence"


def save_evidence(
    session: Session,
    sighting_id: str,
    kind: EvidenceKind,
    image: np.ndarray,
    observed_at: datetime,
    base_dir: Path | None = None,
) -> Evidence:
    """Write the image as JPEG under data/evidence/YYYY/MM/DD/ and record it."""
    base_dir = base_dir or EVIDENCE_DIR
    ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise ValueError("Could not encode evidence image")
    data = encoded.tobytes()
    folder = base_dir / observed_at.strftime("%Y/%m/%d")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sighting_id}_{kind.lower()}.jpg"
    path.write_bytes(data)

    days = load_yaml("settings.yaml")["evidence"]["evidence_retention_days"]
    evidence = Evidence(
        sighting_id=sighting_id,
        kind=kind,
        path=(
            path.relative_to(ROOT_DIR).as_posix()
            if path.is_relative_to(ROOT_DIR)
            else str(path)
        ),
        sha256=hashlib.sha256(data).hexdigest(),
        purge_after=observed_at + timedelta(days=days),
    )
    session.add(evidence)
    return evidence
