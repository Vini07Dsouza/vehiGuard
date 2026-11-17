"""Rebuild the VehiGuard dummy database with one command (Phase 1, tasks 1.4-1.7).

    python scripts/seed_data.py

It applies all migrations, EMPTIES every table, then loads stations, cameras,
vehicles, stolen/missing reports and users. Owner names and FIR references
are fictional. Every acceptance scenario (S01-S17) has matching records.
"""

import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # allow "python scripts/seed_data.py"

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.core.config import get_settings
from app.db.models import (
    Base,
    Camera,
    PoliceStation,
    StatusHistory,
    Vehicle,
    VehicleReport,
)
from app.db.repositories import UserRepository
from app.db.session import SessionLocal, engine
from app.domain.geo import haversine_km
from app.domain.states import (
    CameraSourceType,
    HistoryEntity,
    RecoveryStatus,
    ReportType,
    Role,
)
from app.services.audit import append_audit, verify_chain

# (station_id, name, lat, lon)
STATIONS = [
    ("PS01", "City Central Police Station", 12.9716, 77.5946),
    ("PS02", "North Police Station", 13.0358, 77.5970),
    ("PS03", "Highway Police Station", 12.7500, 77.3400),
]

# (camera_id, station_id, name, lat, lon, source_type, source_url)
# CAM-A to CAM-B is about 7 km (plausible journeys, S02).
# CAM-A to CAM-C is about 38 km (impossible journeys, S05/S06).
CAMERAS = [
    ("CAM-A", "PS01", "Central Junction", 12.9716, 77.5946,
     CameraSourceType.PHONE_STREAM, "http://192.168.1.2:8080/video"),
    ("CAM-B", "PS02", "North Junction", 13.0358, 77.5970,
     CameraSourceType.VIDEO_FILE, "data/test_sessions/cam_b.mp4"),
    ("CAM-C", "PS03", "Mysuru Road Toll", 12.7420, 77.3330,
     CameraSourceType.VIDEO_FILE, "data/test_sessions/cam_c.mp4"),
]  # fmt: skip

W, BK, R, BL, G, Y, BR = (
    "WHITE_SILVER_GREY", "BLACK", "RED", "BLUE", "GREEN", "YELLOW_ORANGE", "BROWN",
)  # fmt: skip
CAR, BIKE, BUS, TRUCK = "CAR", "MOTORCYCLE", "BUS", "TRUCK"

# (plate, type, make, model, colour family, fictional owner)
VEHICLES = [
    ("KA19AB1234", CAR, "Maruti", "Swift", W, "Arun Kumar"),        # S01, S11
    ("KA20EF2468", CAR, "Tata", "Nexon", BL, "Meera Nair"),         # S02, S17
    ("KA19EG2310", CAR, "Hyundai", "i20", R, "Rohan Shetty"),       # S05 clone
    ("KA22JK9753", CAR, "Ford", "Figo", W, "Divya Rao"),            # S06 clone
    ("KA21GH1357", CAR, "Toyota", "Innova", W, "Suresh Pai"),       # S03, S10, S12
    ("KA24PQ1122", CAR, "Maruti", "Alto", G, "Kavya Bhat"),         # S04
    ("KA01MX4455", CAR, "Maruti", "Dzire", W, "Nikhil Hegde"),      # S07
    ("KA51AC3344", CAR, "Mahindra", "XUV700", BK, "Anil Gowda"),    # S14
    ("KA53Z9012", CAR, "Hyundai", "Creta", W, "Pooja Kamath"),
    ("KA02HJ5566", CAR, "Toyota", "Fortuner", W, "Vikram Naik"),
    ("KA04KL6677", BIKE, "Bajaj", "Pulsar 150", R, "Sanjay Acharya"),
    ("KA19TR0001", CAR, "Honda", "City", W, "Lakshmi Prabhu"),
    ("KA19TR0002", CAR, "Kia", "Seltos", BK, "Harish Shenoy"),
    ("HR98AA7777", TRUCK, "Tata", "Signa", Y, "Rajesh Yadav"),
    ("KA05MH2201", BIKE, "Honda", "Activa", BK, "Sneha Kulkarni"),
    ("KA03NB7788", BIKE, "Royal Enfield", "Classic 350", BK, "Manoj Rai"),
    ("KA09P4321", BUS, "Ashok Leyland", "Viking", R, "Mysuru City Transport"),
    ("KA41MB1020", CAR, "Renault", "Kwid", R, "Asha Poojary"),
    ("KA50N3030", CAR, "Honda", "Amaze", BR, "Deepak Salian"),
    ("KA19MD4040", CAR, "Maruti", "Ertiga", W, "Priya D'Souza"),
    ("KA20Z6020", CAR, "Toyota", "Glanza", BL, "Ganesh Bhandary"),
    ("KA70H5230", CAR, "Maruti", "Baleno", W, "Shreya Karanth"),
    ("KA19HP5739", BIKE, "TVS", "Jupiter", W, "Akash Moily"),
    ("KL12MP5537", CAR, "Maruti", "WagonR", W, "Fathima Rahman"),
    ("22BH4545AB", CAR, "Skoda", "Slavia", BL, "Karthik Iyer"),
]  # fmt: skip

# (plate, type, fictional FIR, place, days ago, recovery status)
REPORTS = [
    ("KA21GH1357", ReportType.STOLEN, "FIR-DEMO-001/2026", "MG Road, Bengaluru",
     10, RecoveryStatus.REPORTED),                                   # S03, S12
    ("KA24PQ1122", ReportType.MISSING, "FIR-DEMO-002/2026", "Jayanagar, Bengaluru",
     6, RecoveryStatus.REPORTED),                                    # S04
    ("KA51AC3344", ReportType.STOLEN, "FIR-DEMO-003/2026", "Hebbal, Bengaluru",
     15, RecoveryStatus.DETECTED),                                   # S14
    ("KA53Z9012", ReportType.STOLEN, "FIR-DEMO-004/2026", "Kengeri, Bengaluru",
     20, RecoveryStatus.UNDER_INVESTIGATION),
    ("KA02HJ5566", ReportType.STOLEN, "FIR-DEMO-005/2026", "Whitefield, Bengaluru",
     40, RecoveryStatus.RECOVERED),
    ("KA04KL6677", ReportType.MISSING, "FIR-DEMO-006/2026", "Yelahanka, Bengaluru",
     60, RecoveryStatus.CLOSED),
]  # fmt: skip

# Path each seeded report took to reach its current status
STATUS_PATH = {
    RecoveryStatus.REPORTED: [],
    RecoveryStatus.DETECTED: [RecoveryStatus.DETECTED],
    RecoveryStatus.UNDER_INVESTIGATION: [
        RecoveryStatus.DETECTED,
        RecoveryStatus.UNDER_INVESTIGATION,
    ],
    RecoveryStatus.RECOVERED: [RecoveryStatus.DETECTED, RecoveryStatus.RECOVERED],
    RecoveryStatus.CLOSED: [RecoveryStatus.CLOSED],
}

USERS = [
    ("admin", Role.ADMIN),
    ("officer", Role.POLICE_OFFICER),
    ("operator", Role.CAMERA_OPERATOR),
    ("viewer", Role.VIEWER),  # S16: may not change statuses
]

# Plates that must NOT be in the registry
UNREGISTERED_TEST_PLATES = {
    "KA23MN8642": "S08 unknown plate",
    "KA21GH1358": "S10 one character from stolen KA21GH1357",
}


def migrate() -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "app/db/migrations"))
    command.upgrade(cfg, "head")


def empty_all_tables() -> None:
    names = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as con:
        con.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))


def main() -> None:
    migrate()
    empty_all_tables()
    now = datetime.now(UTC)
    password = get_settings().seed_user_password
    generated = not password
    if generated:
        password = secrets.token_urlsafe(9)

    with SessionLocal() as session:
        for sid, name, lat, lon in STATIONS:
            session.add(
                PoliceStation(
                    station_id=sid,
                    name=name,
                    lat=lat,
                    lon=lon,
                    email=f"{sid.lower()}@example.com",
                )
            )
        session.flush()  # stations before their cameras

        for cid, sid, name, lat, lon, source_type, url in CAMERAS:
            session.add(
                Camera(
                    camera_id=cid,
                    station_id=sid,
                    name=name,
                    lat=lat,
                    lon=lon,
                    source_type=source_type,
                    source_url=url,
                )
            )
        for plate, vtype, make, model, colour, owner in VEHICLES:
            session.add(
                Vehicle(
                    plate_no=plate,
                    vehicle_type=vtype,
                    make=make,
                    model=model,
                    colour_family=colour,
                    owner_name=owner,
                )
            )
        session.flush()  # vehicles before their reports

        users = UserRepository(session)
        officer_id = None
        for username, role in USERS:
            user = users.create(username, password, role)
            if role == Role.POLICE_OFFICER:
                officer_id = user.user_id

        for plate, rtype, fir, place, days_ago, status in REPORTS:
            report = VehicleReport(
                plate_no=plate,
                report_type=rtype,
                fir_ref=fir,
                reported_at=now - timedelta(days=days_ago),
                reported_place=place,
                recovery_status=status,
            )
            session.add(report)
            session.flush()
            previous = RecoveryStatus.REPORTED
            for step in STATUS_PATH[status]:
                session.add(
                    StatusHistory(
                        entity_type=HistoryEntity.REPORT,
                        entity_id=report.report_id,
                        from_status=previous,
                        to_status=step,
                        user_id=officer_id,
                        note="Seed data",
                    )
                )
                previous = step

        append_audit(
            session,
            action="SEED_DATABASE",
            entity="database",
            details={
                "stations": len(STATIONS),
                "cameras": len(CAMERAS),
                "vehicles": len(VEHICLES),
                "reports": len(REPORTS),
                "users": len(USERS),
            },
        )
        session.commit()

        registered = {v[0] for v in VEHICLES}
        assert not registered & set(UNREGISTERED_TEST_PLATES), "test plate registered"
        ok, broken = verify_chain(session)
        assert ok, f"audit chain broken at {broken}"

    cams = {c[0]: c for c in CAMERAS}

    def km(a: str, b: str) -> float:
        return haversine_km(cams[a][3], cams[a][4], cams[b][3], cams[b][4])

    print("VehiGuard dummy database rebuilt")
    print(f"  stations {len(STATIONS)}, cameras {len(CAMERAS)}, ", end="")
    print(f"vehicles {len(VEHICLES)}, reports {len(REPORTS)}, users {len(USERS)}")
    print(f"  CAM-A to CAM-B: {km('CAM-A', 'CAM-B'):.1f} km (plausible journeys)")
    print(f"  CAM-A to CAM-C: {km('CAM-A', 'CAM-C'):.1f} km (impossible journeys)")
    print("  Unregistered test plates:", ", ".join(UNREGISTERED_TEST_PLATES))
    print("  Audit chain: OK")
    print("  Users:", ", ".join(u for u, _ in USERS))
    if generated:
        print(f"  Demo password for all users (shown once): {password}")
        print("  Set SEED_USER_PASSWORD in .env to choose your own.")
    else:
        print("  Demo password: SEED_USER_PASSWORD from .env")


if __name__ == "__main__":
    main()
