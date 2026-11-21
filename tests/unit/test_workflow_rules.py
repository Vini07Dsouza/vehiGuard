"""The permission matrix and status transition tables, checked pair by pair."""

import itertools

import pytest

from app.domain.permissions import PERMISSIONS, Action, can
from app.domain.states import (
    ALERT_TRANSITIONS,
    OPEN_ALERT_STATUSES,
    RECOVERY_TRANSITIONS,
    AlertStatus,
    RecoveryStatus,
    Role,
)

A, R = AlertStatus, RecoveryStatus
O, CO, AD, V = Role.POLICE_OFFICER, Role.CAMERA_OPERATOR, Role.ADMIN, Role.VIEWER

# Written out in full from architecture section 10 (the Roles column)
EXPECTED_ROLES = {
    Action.VIEW_SIGHTINGS: {O, CO, AD, V},
    Action.VIEW_ALERTS: {O, AD, V},
    Action.VIEW_REPORTS: {O, AD, V},
    Action.VIEW_ANALYTICS: {O, AD, V},
    Action.VIEW_AUDIT: {AD, V},
    Action.CHANGE_ALERT_STATUS: {O},
    Action.CREATE_REPORT: {O, AD},
    Action.CHANGE_RECOVERY_STATUS: {O},
    Action.MANAGE_CAMERAS: {CO, AD},
    Action.MANAGE_RECORDS: {AD},
    Action.RUN_RETENTION: {AD},
}


def test_every_action_is_in_the_matrix():
    assert set(PERMISSIONS) == set(Action) == set(EXPECTED_ROLES)


@pytest.mark.parametrize(("action", "role"), itertools.product(Action, Role))
def test_permission_matrix_pair(action, role):
    assert can(role, action) is (role in EXPECTED_ROLES[action])


def test_viewer_and_operator_can_change_no_status():  # S16
    for role in (V, CO):
        assert not can(role, Action.CHANGE_ALERT_STATUS)
        assert not can(role, Action.CHANGE_RECOVERY_STATUS)


# Architecture section 6.2 (alerts) and section 6.3 (recovery), as pairs
ALERT_ALLOWED = {
    (A.NEW, A.ACKNOWLEDGED),
    (A.NEW, A.UNDER_INVESTIGATION),
    (A.NEW, A.CLOSED_FALSE_ALARM),
    (A.ACKNOWLEDGED, A.UNDER_INVESTIGATION),
    (A.ACKNOWLEDGED, A.CLOSED_FALSE_ALARM),
    (A.UNDER_INVESTIGATION, A.CLOSED_CONFIRMED),
    (A.UNDER_INVESTIGATION, A.CLOSED_FALSE_ALARM),
}
RECOVERY_ALLOWED = {
    (R.REPORTED, R.DETECTED),
    (R.REPORTED, R.CLOSED),
    (R.DETECTED, R.UNDER_INVESTIGATION),
    (R.DETECTED, R.REPORTED),
    (R.DETECTED, R.RECOVERED),
    (R.DETECTED, R.CLOSED),
    (R.UNDER_INVESTIGATION, R.RECOVERED),
    (R.UNDER_INVESTIGATION, R.DETECTED),
    (R.UNDER_INVESTIGATION, R.REPORTED),
    (R.UNDER_INVESTIGATION, R.CLOSED),
    (R.RECOVERED, R.CLOSED),
}


@pytest.mark.parametrize(("old", "new"), itertools.product(AlertStatus, AlertStatus))
def test_alert_transition_pair(old, new):
    assert (new in ALERT_TRANSITIONS[old]) is ((old, new) in ALERT_ALLOWED)


@pytest.mark.parametrize(
    ("old", "new"), itertools.product(RecoveryStatus, RecoveryStatus)
)
def test_recovery_transition_pair(old, new):
    assert (new in RECOVERY_TRANSITIONS[old]) is ((old, new) in RECOVERY_ALLOWED)


def test_closed_alerts_are_final_and_only_open_ones_count_as_open():
    assert ALERT_TRANSITIONS[A.CLOSED_CONFIRMED] == set()
    assert ALERT_TRANSITIONS[A.CLOSED_FALSE_ALARM] == set()
    assert OPEN_ALERT_STATUSES == {A.NEW, A.ACKNOWLEDGED, A.UNDER_INVESTIGATION}


def test_a_clone_is_never_confirmed_automatically():  # FR-CLN-06
    # The only way into CLOSED_CONFIRMED is a change by an officer
    assert {r for r in Role if can(r, Action.CHANGE_ALERT_STATUS)} == {O}
