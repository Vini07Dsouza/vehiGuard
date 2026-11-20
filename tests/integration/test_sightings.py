"""Recording sightings with evidence (FR-PLT-07/09). Rolled back afterwards."""

import hashlib
import time
from pathlib import Path

import numpy as np
import pytest

from app.db.models import Camera, Evidence, PoliceStation, Vehicle
from app.pipeline.plate_validator import VoteStatus
from app.services import evidence as evidence_module
from app.services.sightings import PlateEvent, record_sighting

pytestmark = pytest.mark.db


@pytest.fixture
def camera(session, tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_module, "EVIDENCE_DIR", tmp_path)
    session.add(PoliceStation(station_id="T-PS", name="T", lat=0, lon=0, email="t@x"))
    session.flush()
    session.add(
        Camera(
            camera_id="T-CAM",
            station_id="T-PS",
            name="T",
            lat=0,
            lon=0,
            source_type="VIDEO_FILE",
        )
    )
    session.add(
        Vehicle(
            plate_no="TS09AB0001",
            vehicle_type="CAR",
            make="T",
            model="T",
            colour_family="RED",
            owner_name="T",
        )
    )
    session.flush()
    return "T-CAM"


def event(status, plate=None, with_images=True):
    img = np.full((60, 80, 3), 128, np.uint8) if with_images else None
    return PlateEvent(
        camera_id="T-CAM",
        status=status,
        observed_at=time.time(),
        plate=plate,
        confidence=0.9 if plate else None,
        vehicle_image=img,
        plate_image=img,
        stage_ms={"total": 123.4},
    )


@pytest.mark.parametrize(
    ("status", "plate", "outcome"),
    [
        (VoteStatus.ACCEPTED, "TS09AB0001", "PASS"),  # registered
        (VoteStatus.ACCEPTED, "TS09ZZ9999", "UNKNOWN_PLATE"),  # not registered
        (VoteStatus.NO_PLATE, None, "NO_PLATE"),
        (VoteStatus.LOW_CONFIDENCE, None, "LOW_CONFIDENCE"),
    ],
)
def test_outcomes(session, camera, status, plate, outcome):
    sighting = record_sighting(session, event(status, plate)).sighting
    assert sighting.outcome == outcome
    assert sighting.total_ms == 123.4


def test_evidence_files_are_saved_with_fingerprint(session, camera, tmp_path):
    sighting = record_sighting(
        session, event(VoteStatus.ACCEPTED, "TS09AB0001")
    ).sighting
    session.flush()
    rows = session.query(Evidence).filter_by(sighting_id=sighting.sighting_id).all()
    assert sorted(r.kind for r in rows) == ["PLATE_CROP", "VEHICLE_FRAME"]
    for row in rows:
        data = Path(row.path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row.sha256
        assert row.purge_after > sighting.observed_at


def test_no_images_means_no_evidence_rows(session, camera):
    sighting = record_sighting(
        session, event(VoteStatus.NO_PLATE, with_images=False)
    ).sighting
    session.flush()
    assert not session.query(Evidence).filter_by(sighting_id=sighting.sighting_id).all()
