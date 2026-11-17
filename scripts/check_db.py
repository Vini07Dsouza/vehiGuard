"""Phase 0 check: create the VehiGuard database if needed and connect to it.

Run from the project folder:  python -m scripts.check_db
"""

import sys

import psycopg
from sqlalchemy import make_url, text

from app.core.config import get_settings

url = make_url(get_settings().database_url)
if url.password in (None, "", "CHANGE_ME"):
    sys.exit("Set your PostgreSQL password in DATABASE_URL in .env first.")

# 1. Connect to the built-in "postgres" database and create ours if missing
server = {
    "host": url.host,
    "port": url.port or 5432,
    "user": url.username,
    "password": url.password,
}
with psycopg.connect(dbname="postgres", autocommit=True, **server) as con:
    exists = con.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
    ).fetchone()
    if exists:
        print(f"Database '{url.database}' already exists")
    else:
        con.execute(f'CREATE DATABASE "{url.database}"')
        print(f"Created database '{url.database}'")

# 2. Connect through SQLAlchemy, the same way the app does
from app.db.session import engine

with engine.connect() as con:
    version = con.execute(text("SELECT version()")).scalar()
    print("Connected:", version.split(",")[0])
print("OK")
