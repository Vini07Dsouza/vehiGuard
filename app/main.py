"""VehiGuard backend API.

Run from the project folder:  uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routers import router
from app.api.views import router as views_router
from app.db.session import engine

app = FastAPI(title="VehiGuard API", version="0.1.0")
app.include_router(router)
app.include_router(views_router)


@app.get("/api/v1/health")
def health() -> dict:
    """Phase 0 check: the API is up and can reach the database."""
    try:
        with engine.connect() as con:
            con.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError as exc:  # report the failure instead of crashing
        database = f"error: {type(exc).__name__}"
    return {"api": "ok", "database": database}
