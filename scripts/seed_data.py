"""Fill the database with dummy data. Safe to run many times."""

from datetime import date, timedelta

from app.db.models import Checkpoint, Owner, PoliceStation, Vehicle
from app.db.session import SessionLocal, init_db

# (station_id, name, lat, lon)  - sample coordinates, replace with your own
STATIONS = [
    ("PS01", "City Central Police Station", 12.9716, 77.5946),
    ("PS02", "North Police Station", 13.0358, 77.5970),
    ("PS03", "South Police Station", 12.9166, 77.6101),
]

# (checkpoint_id, station_id, name, lat, lon)
CHECKPOINTS = [
    ("CP01", "PS01", "Main Road Checkpoint", 12.9750, 77.6000),
    ("CP02", "PS02", "North Junction Checkpoint", 13.0300, 77.5950),
]

# (owner_id, fictional name, volunteer code)
OWNERS = [
    ("O001", "Arun Kumar", "V01"),
    ("O002", "Meera Nair", "V02"),
    ("O003", "Rohan Shetty", "V03"),
]

# (plate, owner_id, type, valid_for_days, status, make, model, colour)
# valid_for_days: None for permanent, +N = valid for N more days, -N = expired
VEHICLES = [
    ("KA19AB1234", "O001", "PERMANENT", None, "ACTIVE", "Maruti", "Swift", "White"),
    ("KA19CD5678", "O002", "PERMANENT", None, "ACTIVE", "Hyundai", "i20", "Red"),
    ("KA20EF2468", "O003", "PERMANENT", None, "ACTIVE", "Tata", "Nexon", "Blue"),
    ("KA19TR0001", "O003", "TEMPORARY", 20, "ACTIVE", "Honda", "City", "Silver"),
    ("KA19TR0002", "O001", "TEMPORARY", -10, "ACTIVE", "Kia", "Seltos", "Black"),
    ("KA21GH1357", "O002", "PERMANENT", None, "STOLEN", "Toyota", "Innova", "White"),
    ("KA22JK9753", None, "PERMANENT", None, "BLACKLISTED", "Ford", "Figo", "Grey"),
    ("KA24PQ1122", "O003", "PERMANENT", None, "MISSING", "Maruti", "Alto", "Green"),
    # KA23MN8642 is deliberately NOT in this list: it tests "unregistered"
]


def main() -> None:
    init_db()
    today = date.today()  # noqa: DTZ011
    with SessionLocal() as session:
        # 1. Stations first (checkpoints refer to them)
        for sid, name, lat, lon in STATIONS:
            session.merge(
                PoliceStation(
                    station_id=sid,
                    name=name,
                    lat=lat,
                    lon=lon,
                    email=f"{sid.lower()}@example.com",
                )
            )
        session.commit()

        # 2. Checkpoints and owners
        for cid, sid, name, lat, lon in CHECKPOINTS:
            session.merge(
                Checkpoint(
                    checkpoint_id=cid, station_id=sid, name=name, lat=lat, lon=lon
                )
            )
        for oid, name, code in OWNERS:
            session.merge(Owner(owner_id=oid, full_name=name, consent_ref=code))
        session.commit()

        # 3. Vehicles last (they refer to owners)
        for plate, oid, rtype, days, status, make, model, colour in VEHICLES:
            session.merge(
                Vehicle(
                    plate_no=plate,
                    owner_id=oid,
                    registration_type=rtype,
                    valid_until=today + timedelta(days=days) if days else None,
                    status=status,
                    make=make,
                    model=model,
                    colour=colour,
                )
            )
        session.commit()

        print("Stations:   ", session.query(PoliceStation).count())
        print("Checkpoints:", session.query(Checkpoint).count())
        print("Owners:     ", session.query(Owner).count())
        print("Vehicles:   ", session.query(Vehicle).count())


if __name__ == "__main__":
    main()
