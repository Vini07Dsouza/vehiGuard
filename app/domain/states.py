"""Fixed values used across VehiGuard (PRD §4-5, architecture §6-7)."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    POLICE_OFFICER = "POLICE_OFFICER"
    CAMERA_OPERATOR = "CAMERA_OPERATOR"
    VIEWER = "VIEWER"


class VehicleType(StrEnum):
    CAR = "CAR"
    MOTORCYCLE = "MOTORCYCLE"
    BUS = "BUS"
    TRUCK = "TRUCK"
    UNKNOWN = "UNKNOWN"


class ColourFamily(StrEnum):
    WHITE_SILVER_GREY = "WHITE_SILVER_GREY"
    BLACK = "BLACK"
    RED = "RED"
    BLUE = "BLUE"
    GREEN = "GREEN"
    YELLOW_ORANGE = "YELLOW_ORANGE"
    BROWN = "BROWN"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class ReportType(StrEnum):
    STOLEN = "STOLEN"
    MISSING = "MISSING"


class RecoveryStatus(StrEnum):
    REPORTED = "REPORTED"
    DETECTED = "DETECTED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    RECOVERED = "RECOVERED"
    CLOSED = "CLOSED"


# Reports in these states are matched against sightings (architecture §6.3)
ACTIVE_RECOVERY_STATUSES = frozenset(
    {
        RecoveryStatus.REPORTED,
        RecoveryStatus.DETECTED,
        RecoveryStatus.UNDER_INVESTIGATION,
    }
)

RECOVERY_TRANSITIONS = {
    RecoveryStatus.REPORTED: {RecoveryStatus.DETECTED, RecoveryStatus.CLOSED},
    RecoveryStatus.DETECTED: {
        RecoveryStatus.UNDER_INVESTIGATION,
        RecoveryStatus.REPORTED,
        RecoveryStatus.RECOVERED,
        RecoveryStatus.CLOSED,
    },
    RecoveryStatus.UNDER_INVESTIGATION: {
        RecoveryStatus.RECOVERED,
        RecoveryStatus.DETECTED,
        RecoveryStatus.REPORTED,
        RecoveryStatus.CLOSED,
    },
    RecoveryStatus.RECOVERED: {RecoveryStatus.CLOSED},
    RecoveryStatus.CLOSED: set(),
}


class SightingOutcome(StrEnum):
    PASS = "PASS"
    STOLEN_MATCH = "STOLEN_MATCH"
    MISSING_MATCH = "MISSING_MATCH"
    SUSPECTED_CLONE = "SUSPECTED_CLONE"
    APPEARANCE_MISMATCH = "APPEARANCE_MISMATCH"
    UNKNOWN_PLATE = "UNKNOWN_PLATE"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NO_PLATE = "NO_PLATE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    ERROR = "ERROR"


class AlertType(StrEnum):
    STOLEN_VEHICLE = "STOLEN_VEHICLE"
    MISSING_VEHICLE = "MISSING_VEHICLE"
    SUSPECTED_CLONE = "SUSPECTED_CLONE"
    APPEARANCE_MISMATCH = "APPEARANCE_MISMATCH"
    UNREGISTERED_VEHICLE = "UNREGISTERED_VEHICLE"


class Severity(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class AlertStatus(StrEnum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    CLOSED_CONFIRMED = "CLOSED_CONFIRMED"
    CLOSED_FALSE_ALARM = "CLOSED_FALSE_ALARM"


class CameraSourceType(StrEnum):
    PHONE_STREAM = "PHONE_STREAM"
    VIDEO_FILE = "VIDEO_FILE"
    IMAGE_FOLDER = "IMAGE_FOLDER"


class CameraStatus(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    STOPPED = "STOPPED"


class EvidenceKind(StrEnum):
    VEHICLE_FRAME = "VEHICLE_FRAME"
    PLATE_CROP = "PLATE_CROP"


class OutboxChannel(StrEnum):
    EMAIL = "EMAIL"
    SIMULATED = "SIMULATED"


class OutboxStatus(StrEnum):
    QUEUED = "QUEUED"
    SENDING = "SENDING"
    RETRYING = "RETRYING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class HistoryEntity(StrEnum):
    ALERT = "ALERT"
    REPORT = "REPORT"
