"""Dashboard read endpoints: sightings, timeline, cameras, health, evidence images."""

import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_session
from app.core.security import hash_password
from app.db.models import Camera, Evidence, PoliceStation, User, Vehicle, VehicleReport
from app.domain.states import Role
from app.main import app
from app.pipeline.plate_validator import VoteStatus
from app.services import alerts as alerts_module
from app.services import evidence as evidence_module
from app.services.sightings import PlateEvent, record_sighting

pytestmark = pytest.mark.db

PASSWORD = "Test-pass-123"  # a test value, only used in rolled-back tests
PASSWORD_HASH = hash_password(PASSWORD)
STOLEN, OTHER = "TS14AB1001", "TS14CD2002"
SECRET = "test-only-signing-key-0123456789abcdef"


@pytest.fixture
def api(session, tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_module, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr("app.core.security.get_settings", lambda: SimpleNamespace(jwt_secret=SECRET))  # fmt: skip
    alerts_module.clear_station_cache()
    session.add(PoliceStation(station_id="T-PS", name="Test PS", lat=20, lon=80,
                              email="ps@test.local"))  # fmt: skip
    session.flush()
    for cam, lat in (("T-A", 20.00), ("T-B", 20.06)):
        session.add(Camera(camera_id=cam, station_id="T-PS", name=f"Camera {cam}",
                           lat=lat, lon=80, source_type="PHONE_STREAM"))  # fmt: skip
    for plate in (STOLEN, OTHER):
        session.add(Vehicle(plate_no=plate, vehicle_type="CAR", make="Tata", model="Nexon",
                            colour_family="RED", owner_name="Test Owner"))  # fmt: skip
    session.flush()
    session.add(VehicleReport(plate_no=STOLEN, report_type="STOLEN", fir_ref="FIR-T14",
                              reported_at=datetime.now(UTC), reported_place="Test"))  # fmt: skip
    for name, role in (
        ("t14_officer", Role.POLICE_OFFICER),
        ("t14_viewer", Role.VIEWER),
        ("t14_operator", Role.CAMERA_OPERATOR),
    ):
        session.add(User(username=name, password_hash=PASSWORD_HASH, role=role))  # fmt: skip
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
    alerts_module.clear_station_cache()


def token(client, who):
    reply = client.post("/api/v1/auth/login",
                        json={"username": f"t14_{who}", "password": PASSWORD})  # fmt: skip
    return {"Authorization": f"Bearer {reply.json()['access_token']}"}


def see(session, camera, plate, seconds_ago=0.0):
    img = np.full((40, 80, 3), 90, np.uint8)
    result = record_sighting(
        session,
        PlateEvent(camera_id=camera, status=VoteStatus.ACCEPTED,
                   observed_at=time.time() - seconds_ago, plate=plate, confidence=0.9,
                   vehicle_image=img, plate_image=img),
    )  # fmt: skip
    session.flush()
    return result


def mine(rows, key="plate_no", values=(STOLEN, OTHER)):
    return [r for r in rows if r[key] in values]


# ----------------------------------------------------------------------- /me
@pytest.mark.parametrize(
    ("who", "can_change", "can_see_alerts"),
    [("officer", True, True), ("viewer", False, True), ("operator", False, False)],
)
def test_me_tells_the_dashboard_what_the_user_may_do(
    api, who, can_change, can_see_alerts
):
    me = api.get("/api/v1/me", headers=token(api, who)).json()
    assert me["username"] == f"t14_{who}"
    assert ("CHANGE_ALERT_STATUS" in me["permissions"]) is can_change
    assert ("VIEW_ALERTS" in me["permissions"]) is can_see_alerts


def test_me_needs_a_token(api):
    assert api.get("/api/v1/me").status_code == 401


# ------------------------------------------------------------------ sightings
def test_sightings_list_with_filters_and_evidence(api, session):
    see(session, "T-A", OTHER, seconds_ago=30)
    see(session, "T-B", STOLEN)
    rows = api.get("/api/v1/sightings?limit=200", headers=token(api, "operator")).json()
    mine_rows = mine(rows)
    assert [r["plate_no"] for r in mine_rows] == [STOLEN, OTHER]  # newest first
    assert mine_rows[0]["camera"] == {"id": "T-B", "name": "Camera T-B", "lat": 20.06, "lon": 80.0}  # fmt: skip
    assert mine_rows[0]["outcome"] == "STOLEN_MATCH"
    assert {e["kind"] for e in mine_rows[0]["evidence"]} == {
        "VEHICLE_FRAME",
        "PLATE_CROP",
    }
    by_plate = api.get(
        "/api/v1/sightings?plate=ts14ab", headers=token(api, "viewer")
    ).json()
    assert {r["plate_no"] for r in by_plate} == {STOLEN}
    by_camera = api.get(
        "/api/v1/sightings?camera_id=T-A", headers=token(api, "viewer")
    ).json()
    assert [r["plate_no"] for r in by_camera] == [OTHER]
    by_outcome = api.get("/api/v1/sightings?outcome=PASS&limit=200", headers=token(api, "viewer")).json()  # fmt: skip
    assert OTHER in [r["plate_no"] for r in by_outcome] and STOLEN not in [r["plate_no"] for r in by_outcome]  # fmt: skip


def test_sightings_since_filter_and_bad_input(api, session):
    see(session, "T-A", OTHER, seconds_ago=3600)
    recent = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    rows = api.get("/api/v1/sightings", params={"since": recent, "camera_id": "T-A"},
                   headers=token(api, "viewer")).json()  # fmt: skip
    assert rows == []
    assert api.get("/api/v1/sightings?limit=9999", headers=token(api, "viewer")).status_code == 422  # fmt: skip
    assert api.get("/api/v1/sightings?outcome=BOGUS", headers=token(api, "viewer")).status_code == 422  # fmt: skip


# ------------------------------------------------------------------- timeline
def test_plate_timeline_across_cameras(api, session):
    see(session, "T-A", STOLEN, seconds_ago=600)
    see(session, "T-B", STOLEN)
    data = api.get(f"/api/v1/plates/{STOLEN.lower()}/timeline", headers=token(api, "officer")).json()  # fmt: skip
    assert data["plate_no"] == STOLEN
    assert [s["camera"]["id"] for s in data["sightings"]] == [
        "T-A",
        "T-B",
    ]  # oldest first
    assert data["registry"]["make"] == "Tata"
    assert [a["alert_type"] for a in data["alerts"]] == ["STOLEN_VEHICLE"]
    assert [r["fir_ref"] for r in data["reports"]] == ["FIR-T14"]


def test_timeline_hides_alerts_and_reports_from_roles_without_access(api, session):
    see(session, "T-A", STOLEN)
    data = api.get(
        f"/api/v1/plates/{STOLEN}/timeline", headers=token(api, "operator")
    ).json()
    assert (
        len(data["sightings"]) == 1 and data["alerts"] == [] and data["reports"] == []
    )


def test_timeline_for_an_unknown_plate_is_empty_and_bad_plates_are_rejected(api):
    data = api.get(
        "/api/v1/plates/TS99ZZ0000/timeline", headers=token(api, "viewer")
    ).json()
    assert data["sightings"] == [] and data["registry"] is None
    assert (
        api.get("/api/v1/plates/x!/timeline", headers=token(api, "viewer")).status_code
        == 422
    )


# -------------------------------------------------------------------- cameras
def test_camera_online_only_while_frames_keep_arriving(api, session):
    fresh, stale = session.get(Camera, "T-A"), session.get(Camera, "T-B")
    fresh.status, fresh.last_frame_at = "ONLINE", datetime.now(UTC)
    stale.status, stale.last_frame_at = "ONLINE", datetime.now(UTC) - timedelta(
        minutes=5
    )
    session.flush()
    cams = {c["camera_id"]: c for c in api.get("/api/v1/cameras", headers=token(api, "operator")).json()}  # fmt: skip
    assert cams["T-A"]["state"] == "ONLINE"
    assert cams["T-B"]["state"] == "OFFLINE"  # says ONLINE but the frames stopped
    assert cams["T-A"]["station"] == "Test PS" and cams["T-A"]["lat"] == 20.0


# --------------------------------------------------------------------- health
def test_system_health_panel(api, session):
    see(session, "T-A", STOLEN)  # an open alert, an open case and a queued email
    health = api.get("/api/v1/system/health", headers=token(api, "viewer")).json()
    assert health["database"] == "ok" and health["cameras_total"] >= 2
    assert health["open_alerts"] >= 1 and health["open_cases"] >= 1
    assert health["last_sighting_at"] is not None
    assert health["alert_mode"] in ("simulated", "live")


# ------------------------------------------------------------ evidence images
def evidence_id(session, kind="PLATE_CROP"):
    return session.scalars(select(Evidence).where(Evidence.kind == kind)).all()[-1]


def test_evidence_image_for_users_who_may_see_alerts(api, session):
    see(session, "T-A", STOLEN)
    ev = evidence_id(session)
    reply = api.get(
        f"/api/v1/evidence/{ev.evidence_id}/image", headers=token(api, "viewer")
    )
    assert reply.status_code == 200 and reply.headers["content-type"] == "image/jpeg"
    assert reply.content[:2] == b"\xff\xd8"  # a real JPEG


def test_evidence_image_needs_a_token_and_the_right_role(api, session):
    see(session, "T-A", STOLEN)
    url = f"/api/v1/evidence/{evidence_id(session).evidence_id}/image"
    assert api.get(url).status_code == 401
    assert api.get(url, headers=token(api, "operator")).status_code == 403


def test_purged_evidence_is_gone_and_unknown_evidence_is_not_found(api, session):
    see(session, "T-A", STOLEN)
    ev = evidence_id(session)
    ev.purged_at = datetime.now(UTC)
    assert api.get(f"/api/v1/evidence/{ev.evidence_id}/image", headers=token(api, "viewer")).status_code == 410  # fmt: skip
    assert api.get("/api/v1/evidence/nope/image", headers=token(api, "viewer")).status_code == 404  # fmt: skip


def test_evidence_path_outside_the_evidence_folder_is_never_served(
    api, session, tmp_path
):
    see(session, "T-A", STOLEN)
    ev = evidence_id(session)
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("not for download")
    ev.path = str(secret)  # a tampered row pointing outside the evidence folder
    assert api.get(f"/api/v1/evidence/{ev.evidence_id}/image", headers=token(api, "viewer")).status_code == 404  # fmt: skip


# --------------------------------------------------------------- alert filters
def test_alert_list_filters_and_names(api, session):
    see(session, "T-A", STOLEN)
    viewer = token(api, "viewer")
    rows = api.get("/api/v1/alerts?limit=200", headers=viewer).json()
    row = mine(rows)[0]
    assert (row["camera_name"], row["station_name"]) == ("Camera T-A", "Test PS")
    assert row["alert_type"] == "STOLEN_VEHICLE" and row["reason_codes"]
    for query, expected in [
        ("alert_type=STOLEN_VEHICLE", True), ("alert_type=SUSPECTED_CLONE", False),
        ("severity=HIGH", True), ("severity=LOW", False),
        ("station_id=T-PS", True), ("station_id=NOPE", False),
        ("status=NEW", True), ("status=CLOSED_CONFIRMED", False),
        ("plate=ts14ab", True), ("plate=ts14cd", False),
    ]:  # fmt: skip
        found = api.get(f"/api/v1/alerts?limit=200&{query}", headers=viewer).json()
        assert bool(mine(found)) is expected, query
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    assert mine(api.get("/api/v1/alerts", params={"since": future, "limit": 200}, headers=viewer).json()) == []  # fmt: skip


def test_alert_detail_evidence_has_ids_that_load_and_hides_server_paths(api, session):
    """Both evidence sets of a clone alert must be loadable by the dashboard."""
    see(session, "T-A", OTHER, seconds_ago=2)
    # same plate at a camera 6.7 km away, 2 s later: an impossible journey
    second = see(session, "T-B", OTHER)
    clone = next(a for a in second.alerts if a.alert_type == "SUSPECTED_CLONE")
    viewer = token(api, "viewer")
    detail = api.get(f"/api/v1/alerts/{clone.alert_id}", headers=viewer).json()
    items = detail["evidence"] + detail["earlier_sighting"]["evidence"]
    assert len(items) == 4
    for item in items:
        assert item["evidence_id"] and "path" not in item  # no server file paths
        reply = api.get(f"/api/v1/evidence/{item['evidence_id']}/image", headers=viewer)
        assert reply.status_code == 200
