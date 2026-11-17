"""Database connection for VehiLence (SQLite)."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.models import Base

DB_PATH = Path("data/vehilence.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}")


@event.listens_for(engine, "connect")
def _sqlite_settings(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False)


def init_db() -> None:
    Base.metadata.create_all(engine)
