"""Database checks against PostgreSQL. Every test rolls back, so no data is kept.

Needs: alembic upgrade head
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.db.models import Camera, PoliceStation, Sighting
from app.db.session import engine
from app.domain.states import CameraSourceType, SightingOutcome

pytestmark = pytest.mark.db


@pytest.fixture
def session():
    try:
        connection = engine.connect()
    except OperationalError:
        pytest.skip("PostgreSQL is not reachable")
    transaction = connection.begin()
    from sqlalchemy.orm import Session

    with Session(bind=connection) as s:
        yield s
    transaction.rollback()
    connection.close()


def add_camera(session):
    session.add(
        PoliceStation(
            station_id="T-PS", name="Test PS", lat=12.9, lon=77.5, email="t@x"
        )
    )
    session.flush()  # the station must exist before its camera
    session.add(
        Camera(
            camera_id="T-CAM",
            station_id="T-PS",
            name="Test camera",
            lat=12.9,
            lon=77.5,
            source_type=CameraSourceType.PHONE_STREAM,
        )
    )
    session.flush()


def test_unknown_plate_sighting_is_allowed(session):
    add_camera(session)
    session.add(
        Sighting(
            camera_id="T-CAM",
            plate_no="ZZ99ZZ9999",  # not in the registry
            observed_at=datetime.now(UTC),
            outcome=SightingOutcome.UNKNOWN_PLATE,
        )
    )
    session.flush()
    row = session.query(Sighting).filter_by(plate_no="ZZ99ZZ9999").one()
    assert row.vehicle_type == "UNKNOWN"
    assert row.reason_codes == []


def test_invalid_status_value_is_rejected(session):
    add_camera(session)
    with pytest.raises(IntegrityError):
        session.execute(
            text(
                "INSERT INTO sightings (sighting_id, camera_id, vehicle_type,"
                " colour_family, observed_at, outcome, reason_codes, stage_ms)"
                " VALUES ('x', 'T-CAM', 'UNKNOWN', 'UNKNOWN', now(), 'MAYBE',"
                " '[]', '{}')"
            )
        )
