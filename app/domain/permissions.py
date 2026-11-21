"""Who may do what (FR-AUTH-01, task 6.6): the permission matrix.

One table, in one place, checked by every service and API endpoint.
Matches the Roles column of the REST API overview (architecture §10).
"""

from enum import StrEnum

from app.domain.states import Role


class Action(StrEnum):
    VIEW_SIGHTINGS = "VIEW_SIGHTINGS"
    VIEW_ALERTS = "VIEW_ALERTS"
    VIEW_REPORTS = "VIEW_REPORTS"
    VIEW_ANALYTICS = "VIEW_ANALYTICS"
    VIEW_AUDIT = "VIEW_AUDIT"
    CHANGE_ALERT_STATUS = "CHANGE_ALERT_STATUS"
    CREATE_REPORT = "CREATE_REPORT"
    CHANGE_RECOVERY_STATUS = "CHANGE_RECOVERY_STATUS"
    MANAGE_CAMERAS = "MANAGE_CAMERAS"
    MANAGE_RECORDS = "MANAGE_RECORDS"  # vehicles, stations, users
    RUN_RETENTION = "RUN_RETENTION"


R = Role
PERMISSIONS: dict[Action, frozenset[Role]] = {
    Action.VIEW_SIGHTINGS: frozenset({R.POLICE_OFFICER, R.CAMERA_OPERATOR, R.ADMIN, R.VIEWER}),
    Action.VIEW_ALERTS: frozenset({R.POLICE_OFFICER, R.ADMIN, R.VIEWER}),
    Action.VIEW_REPORTS: frozenset({R.POLICE_OFFICER, R.ADMIN, R.VIEWER}),
    Action.VIEW_ANALYTICS: frozenset({R.POLICE_OFFICER, R.ADMIN, R.VIEWER}),
    Action.VIEW_AUDIT: frozenset({R.ADMIN, R.VIEWER}),
    Action.CHANGE_ALERT_STATUS: frozenset({R.POLICE_OFFICER}),
    Action.CREATE_REPORT: frozenset({R.POLICE_OFFICER, R.ADMIN}),
    Action.CHANGE_RECOVERY_STATUS: frozenset({R.POLICE_OFFICER}),
    Action.MANAGE_CAMERAS: frozenset({R.CAMERA_OPERATOR, R.ADMIN}),
    Action.MANAGE_RECORDS: frozenset({R.ADMIN}),
    Action.RUN_RETENTION: frozenset({R.ADMIN}),
}  # fmt: skip


def can(role: Role, action: Action) -> bool:
    return role in PERMISSIONS[action]
