"""Checks on the table definitions and fixed values (no database needed)."""

from app.db.models import Base
from app.domain.states import (
    ACTIVE_RECOVERY_STATUSES,
    RECOVERY_TRANSITIONS,
    RecoveryStatus,
)

TABLES = Base.metadata.tables


def test_all_architecture_tables_exist():
    assert set(TABLES) == {
        "users",
        "police_stations",
        "cameras",
        "vehicles",
        "vehicle_reports",
        "sightings",
        "evidence",
        "alerts",
        "status_history",
        "outbox",
        "audit_log",
    }


def test_sighting_plate_has_no_foreign_key():
    # Unknown plates must be stored too (architecture §7.1)
    assert not TABLES["sightings"].c.plate_no.foreign_keys


def test_sightings_indexed_by_plate_and_time():
    indexes = {tuple(c.name for c in ix.columns) for ix in TABLES["sightings"].indexes}
    assert ("plate_no", "observed_at") in indexes


def test_alert_has_two_sighting_links_for_clones():
    targets = [fk.column.table.name for fk in TABLES["alerts"].foreign_keys]
    assert targets.count("sightings") == 2


def test_every_recovery_status_has_transition_rules():
    assert set(RECOVERY_TRANSITIONS) == set(RecoveryStatus)


def test_closed_is_terminal_and_recovered_only_closes():
    assert RECOVERY_TRANSITIONS[RecoveryStatus.CLOSED] == set()
    assert RECOVERY_TRANSITIONS[RecoveryStatus.RECOVERED] == {RecoveryStatus.CLOSED}


def test_only_open_reports_are_matched():
    assert RecoveryStatus.RECOVERED not in ACTIVE_RECOVERY_STATUSES
    assert RecoveryStatus.CLOSED not in ACTIVE_RECOVERY_STATUSES
    assert RecoveryStatus.REPORTED in ACTIVE_RECOVERY_STATUSES
