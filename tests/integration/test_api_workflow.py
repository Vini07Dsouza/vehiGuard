"""The sign-in, alert and report endpoints with their role checks (Phase 6).

Uses FastAPI's test client against PostgreSQL; everything is rolled back.
"""

import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_session
from app.core.security import create_access_token, hash_password
from app.db.models import AuditLog, Camera, PoliceStation, User, Vehicle, VehicleReport
from app.domain.states import Role
from app.main import app
from app.pipeline.plate_validator import VoteStatus
from app.services import alerts as alerts_module
from app.services import evidence as evidence_module
from app.services.sightings import PlateEvent, record_sighting

pytestmark = pytest.mark.db

PASSWORD = "Test-pass-123"  # a test value, only used in rolled-back tests
PASSWORD_HASH = hash_password(PASSWORD)
STOLEN, OTHER = "TS13AB1001", "TS13CD2002"
SECRET = "test-only-signing-key-0123456789abcdef"


@pytest.fixture
def api(session, tmp_path, monkeypatch):
    monkeypatch.setattr(evidence_module, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr("app.core.security.get_settings", lambda: SimpleNamespace(jwt_secret=SECRET))  # fmt: skip
    alerts_module.clear_station_cache()
    session.add(PoliceStation(station_id="T-PS", name="Test PS", lat=20, lon=80,
                              email="ps@test.local"))  # fmt: skip
    session.flush()
    session.add(Camera(camera_id="T-CAM", station_id="T-PS", name="Cam", lat=20, lon=80,
                       source_type="PHONE_STREAM"))  # fmt: skip
    for plate in (STOLEN, OTHER):
        session.add(Vehicle(plate_no=plate, vehicle_type="CAR", make="T", model="T",
                            colour_family="RED", owner_name="Test"))  # fmt: skip
    session.flush()
    session.add(VehicleReport(plate_no=STOLEN, report_type="STOLEN", fir_ref="FIR-T13",
                              reported_at=datetime.now(UTC), reported_place="Test"))  # fmt: skip
    for name, role in (
        ("t13_officer", Role.POLICE_OFFICER),
        ("t13_viewer", Role.VIEWER),
        ("t13_operator", Role.CAMERA_OPERATOR),
        ("t13_admin", Role.ADMIN),
    ):
        session.add(User(username=name, password_hash=PASSWORD_HASH, role=role))  # fmt: skip
    session.flush()
    app.dependency_overrides[get_session] = lambda: session
    yield TestClient(app)
    app.dependency_overrides.clear()
    alerts_module.clear_station_cache()


def token(client, who):
    reply = client.post("/api/v1/auth/login",
                        json={"username": f"t13_{who}", "password": PASSWORD})  # fmt: skip
    assert reply.status_code == 200, reply.text
    return {"Authorization": f"Bearer {reply.json()['access_token']}"}


def make_alert(session):
    img = np.full((40, 80, 3), 90, np.uint8)
    result = record_sighting(
        session,
        PlateEvent(camera_id="T-CAM", status=VoteStatus.ACCEPTED, observed_at=time.time(),
                   plate=STOLEN, confidence=0.9, vehicle_image=img, plate_image=img),
    )  # fmt: skip
    session.flush()
    return result.alerts[0].alert_id


def denied_audits(session):
    return session.scalars(
        select(AuditLog).where(AuditLog.action == "ACCESS_DENIED")
    ).all()


# ------------------------------------------------------------------ sign in
def test_login_returns_a_token_with_the_role(api):
    reply = api.post("/api/v1/auth/login",
                     json={"username": "t13_officer", "password": PASSWORD})  # fmt: skip
    body = reply.json()
    assert reply.status_code == 200 and body["role"] == "POLICE_OFFICER"
    assert body["token_type"] == "bearer" and body["expires_in_minutes"] == 30


def test_wrong_password_is_refused_and_audited(api, session):
    reply = api.post("/api/v1/auth/login",
                     json={"username": "t13_officer", "password": "wrong"})  # fmt: skip
    assert reply.status_code == 401
    last = session.scalars(select(AuditLog).order_by(AuditLog.seq.desc())).first()
    assert last.action == "LOGIN_FAILED" and last.details["username"] == "t13_officer"


def test_no_token_bad_token_and_expired_token_are_all_401(api, session):
    assert api.get("/api/v1/alerts").status_code == 401
    bad = {"Authorization": "Bearer not.a.token"}
    assert api.get("/api/v1/alerts", headers=bad).status_code == 401
    officer = session.scalar(select(User).where(User.username == "t13_officer"))
    old = datetime.now(UTC) - timedelta(hours=2)
    stale = create_access_token(officer.user_id, "POLICE_OFFICER", now=old)
    assert api.get("/api/v1/alerts", headers={"Authorization": f"Bearer {stale}"}).status_code == 401  # fmt: skip


def test_a_deactivated_user_loses_access_at_once(api, session):
    headers = token(api, "officer")
    session.scalar(select(User).where(User.username == "t13_officer")).is_active = False
    assert api.get("/api/v1/alerts", headers=headers).status_code == 401


def test_a_token_signed_with_another_key_is_refused(api, session):
    from jose import jwt

    officer = session.scalar(select(User).where(User.username == "t13_officer"))
    forged = jwt.encode({"sub": officer.user_id, "exp": time.time() + 600}, "attacker-key", "HS256")  # fmt: skip
    assert api.get("/api/v1/alerts", headers={"Authorization": f"Bearer {forged}"}).status_code == 401  # fmt: skip


# ------------------------------------------------------------------- alerts
def test_alert_status_workflow_over_http(api, session):
    alert_id = make_alert(session)
    officer = token(api, "officer")
    reply = api.post(f"/api/v1/alerts/{alert_id}/status", headers=officer,
                     json={"status": "ACKNOWLEDGED", "note": "Seen by control room"})  # fmt: skip
    assert reply.status_code == 200 and reply.json()["status"] == "ACKNOWLEDGED"
    detail = api.get(f"/api/v1/alerts/{alert_id}", headers=token(api, "viewer")).json()
    assert detail["status"] == "ACKNOWLEDGED" and detail["plate"] == STOLEN
    assert [(h["from"], h["to"], h["note"]) for h in detail["history"]] == [
        ("NEW", "ACKNOWLEDGED", "Seen by control room")
    ]
    assert detail["evidence"] and detail["station"]["id"] == "T-PS"


@pytest.mark.parametrize("who", ["viewer", "operator", "admin"])
def test_s16_only_officers_can_change_an_alert_status(api, session, who):
    alert_id = make_alert(session)
    before = len(denied_audits(session))
    reply = api.post(f"/api/v1/alerts/{alert_id}/status", headers=token(api, who),
                     json={"status": "ACKNOWLEDGED", "note": "trying"})  # fmt: skip
    assert reply.status_code == 403
    assert api.get(f"/api/v1/alerts/{alert_id}",
                   headers=token(api, "viewer")).json()["status"] == "NEW"  # fmt: skip
    assert len(denied_audits(session)) == before + 1  # the attempt was audited


def test_operator_cannot_even_read_alerts(api):
    assert api.get("/api/v1/alerts", headers=token(api, "operator")).status_code == 403


def test_alert_error_cases(api, session):
    alert_id = make_alert(session)
    officer = token(api, "officer")
    url = f"/api/v1/alerts/{alert_id}/status"
    assert api.post(url, headers=officer, json={"status": "CLOSED_CONFIRMED",
                                                "note": "skipping"}).status_code == 409  # fmt: skip
    assert api.post(url, headers=officer, json={"status": "ACKNOWLEDGED",
                                                "note": ""}).status_code == 422  # fmt: skip
    assert api.post(url, headers=officer, json={"status": "MAYBE",
                                                "note": "x"}).status_code == 422  # fmt: skip
    assert api.post("/api/v1/alerts/nope/status", headers=officer,
                    json={"status": "ACKNOWLEDGED", "note": "x"}).status_code == 404  # fmt: skip


def test_alert_list_can_be_filtered_by_status(api, session):
    alert_id = make_alert(session)
    viewer = token(api, "viewer")
    new = api.get("/api/v1/alerts?status=NEW&limit=200", headers=viewer).json()
    assert alert_id in [a["alert_id"] for a in new]
    closed = api.get("/api/v1/alerts?status=CLOSED_CONFIRMED&limit=200", headers=viewer).json()  # fmt: skip
    assert alert_id not in [a["alert_id"] for a in closed]


# ------------------------------------------------------------------ reports
def test_officer_creates_a_report_and_viewer_cannot(api):
    body = {"plate_no": OTHER.lower(), "report_type": "MISSING",
            "fir_ref": "FIR-NEW", "reported_place": "Market road"}  # fmt: skip
    assert api.post("/api/v1/reports", headers=token(api, "viewer"), json=body).status_code == 403  # fmt: skip
    created = api.post("/api/v1/reports", headers=token(api, "officer"), json=body)
    assert created.status_code == 201
    assert created.json()["plate_no"] == OTHER and created.json()["recovery_status"] == "REPORTED"  # fmt: skip
    again = api.post("/api/v1/reports", headers=token(api, "admin"), json=body)
    assert again.status_code == 409  # already open


def test_report_input_is_validated(api):
    officer = token(api, "officer")
    base = {"report_type": "STOLEN", "fir_ref": "F", "reported_place": "P"}
    assert api.post("/api/v1/reports", headers=officer,
                    json={**base, "plate_no": "TS99ZZ0000"}).status_code == 404  # not registered  # fmt: skip
    assert api.post("/api/v1/reports", headers=officer,
                    json={**base, "plate_no": "bad plate!"}).status_code == 422  # fmt: skip
    assert api.post("/api/v1/reports", headers=officer,
                    json={**base, "plate_no": OTHER, "report_type": "LOST"}).status_code == 422  # fmt: skip
    assert api.post("/api/v1/reports", headers=officer,
                    json={"plate_no": OTHER}).status_code == 422  # missing fields  # fmt: skip


def test_s14_recovery_status_over_http_and_s16_refusal(api, session):
    make_alert(session)  # the camera sees the stolen plate: REPORTED -> DETECTED
    report = session.scalar(
        select(VehicleReport).where(VehicleReport.plate_no == STOLEN)
    )
    url = f"/api/v1/reports/{report.report_id}/status"
    viewer, officer = token(api, "viewer"), token(api, "officer")
    refused = api.post(url, headers=viewer, json={"status": "UNDER_INVESTIGATION", "note": "n"})  # fmt: skip
    assert refused.status_code == 403 and report.recovery_status == "DETECTED"
    for status, note, place in (("UNDER_INVESTIGATION", "Patrol sent", "Junction"),
                                ("RECOVERED", "Found", "Yard 4")):  # fmt: skip
        reply = api.post(url, headers=officer,
                         json={"status": status, "note": note, "location": place})  # fmt: skip
        assert reply.status_code == 200 and reply.json()["recovery_status"] == status
    assert api.post(url, headers=officer,
                    json={"status": "DETECTED", "note": "back"}).status_code == 409  # fmt: skip


def test_report_list_and_stats(api, session):
    make_alert(session)
    viewer = token(api, "viewer")
    reports = api.get("/api/v1/reports?limit=200", headers=viewer).json()
    assert STOLEN in [r["plate_no"] for r in reports]
    stats = api.get("/api/v1/reports/stats", headers=viewer).json()
    assert stats["by_status"]["DETECTED"] >= 1 and "median_hours_to_detection" in stats
    assert api.get("/api/v1/reports", headers=token(api, "operator")).status_code == 403


def test_health_stays_public(api):
    assert api.get("/api/v1/health").json()["api"] == "ok"
