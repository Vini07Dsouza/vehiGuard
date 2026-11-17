"""Shared test fixtures."""

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.db.session import engine


@pytest.fixture
def session():
    """A database session whose changes are always rolled back."""
    try:
        connection = engine.connect()
    except OperationalError:
        pytest.skip("PostgreSQL is not reachable")
    transaction = connection.begin()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as s:
        yield s
    transaction.rollback()
    connection.close()
