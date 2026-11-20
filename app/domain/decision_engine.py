"""The decision engine: PRD §5 decision matrix as one pure function (task 3.2).

decide(DecisionInput) -> Decision. No database, no clock, no I/O: the same
inputs and configuration always give the same result (PRD §5 safety rule 3).
Every business rule about outcomes and alerts lives in this file.

Matrix rows (PRD §5):
  1  no plate / low confidence        -> log only
  2  active STOLEN report             -> STOLEN_VEHICLE, HIGH
  3  active MISSING report            -> MISSING_VEHICLE, HIGH
  4  IJ and (AM or RM)                -> SUSPECTED_CLONE, HIGH
  5  IJ only                          -> SUSPECTED_CLONE, MEDIUM
  6  no IJ, AM or RM                  -> APPEARANCE_MISMATCH, LOW (dashboard)
  7  registered, nothing else         -> PASS
  8  not registered, no IJ            -> UNKNOWN_PLATE (alert only if flagged)
Rows 2-3 are independent of rows 4-6: one sighting can raise several alerts.
"""

from dataclasses import dataclass, field

from app.domain.states import (
    AlertType,
    ReasonCode,
    RecoveryStatus,
    ReportType,
    Severity,
    SightingOutcome,
)

EMAIL_SEVERITIES = frozenset({Severity.HIGH, Severity.MEDIUM})  # FR-ALR-03


@dataclass(frozen=True)
class ReportMatch:
    report_id: str
    report_type: ReportType
    recovery_status: RecoveryStatus  # only active reports are passed in


@dataclass(frozen=True)
class DecisionInput:
    read_status: str  # "ACCEPTED", "NO_PLATE" or "LOW_CONFIDENCE"
    plate: str | None = None
    registered: bool = False
    reports: tuple[ReportMatch, ...] = ()  # active reports for this exact plate
    possible_match_plates: tuple[str, ...] = ()  # near-misses of active reports
    impossible_journey: bool = False  # IJ (Phase 4)
    sighting_mismatch: bool = False  # AM (Phase 5)
    registry_mismatch: bool = False  # RM (Phase 5)
    flag_unregistered: bool = False  # config FLAG_UNREGISTERED (decision D-01)


@dataclass(frozen=True)
class AlertSpec:
    alert_type: AlertType
    severity: Severity
    report_id: str | None = None
    reason_codes: tuple[ReasonCode, ...] = ()

    @property
    def email(self) -> bool:
        return self.severity in EMAIL_SEVERITIES


@dataclass(frozen=True)
class Decision:
    outcome: SightingOutcome
    reason_codes: tuple[ReasonCode, ...]
    alerts: tuple[AlertSpec, ...] = ()
    reports_to_detect: tuple[str, ...] = ()  # REPORTED -> DETECTED (FR-CASE-02)
    review_item: bool = False  # POSSIBLE_MATCH for the officer's review list
    use_for_clone_analysis: bool = field(default=False)


def decide(d: DecisionInput) -> Decision:
    # Row 1: nothing reliable was read. Never an alert, never clone analysis.
    if d.read_status == "NO_PLATE" or (d.read_status == "ACCEPTED" and not d.plate):
        return Decision(SightingOutcome.NO_PLATE, (ReasonCode.NO_PLATE,))
    if d.read_status != "ACCEPTED":
        return Decision(SightingOutcome.LOW_CONFIDENCE, (ReasonCode.LOW_CONFIDENCE,))

    reasons: list[ReasonCode] = [
        ReasonCode.REGISTERED if d.registered else ReasonCode.UNKNOWN_PLATE
    ]
    alerts: list[AlertSpec] = []
    detect: list[str] = []
    # RM needs a registry record (row 8 with IJ uses AM only)
    rm = d.registry_mismatch and d.registered
    am = d.sighting_mismatch
    ij = d.impossible_journey

    # Rows 2 and 3: stolen / missing reports
    report_kinds = (
        (ReportType.STOLEN, AlertType.STOLEN_VEHICLE, ReasonCode.STOLEN_REPORT_MATCH),
        (ReportType.MISSING, AlertType.MISSING_VEHICLE, ReasonCode.MISSING_REPORT_MATCH),
    )  # fmt: skip
    for report_type, alert_type, code in report_kinds:
        for report in (r for r in d.reports if r.report_type == report_type):
            alert_reasons = [code]
            if rm:  # the plate may have been copied from this vehicle
                alert_reasons.append(ReasonCode.APPEARANCE_MISMATCH)
            alerts.append(
                AlertSpec(alert_type, Severity.HIGH, report.report_id, tuple(alert_reasons))
            )  # fmt: skip
            if code not in reasons:
                reasons.append(code)
            if report.recovery_status == RecoveryStatus.REPORTED:
                detect.append(report.report_id)

    # Rows 4 to 6: clone and appearance signals
    if ij:
        reasons.append(ReasonCode.IMPOSSIBLE_JOURNEY)
    if am:
        reasons.append(ReasonCode.SIGHTING_APPEARANCE_MISMATCH)
    if rm:
        reasons.append(ReasonCode.REGISTRY_APPEARANCE_MISMATCH)
    signal_reasons = tuple(r for r in reasons if r in _SIGNAL_CODES)
    if ij and (am or rm):  # row 4
        alerts.append(AlertSpec(AlertType.SUSPECTED_CLONE, Severity.HIGH, None, signal_reasons))  # fmt: skip
    elif ij:  # row 5
        alerts.append(AlertSpec(AlertType.SUSPECTED_CLONE, Severity.MEDIUM, None, signal_reasons))  # fmt: skip
    elif am or rm:  # row 6
        alerts.append(AlertSpec(AlertType.APPEARANCE_MISMATCH, Severity.LOW, None, signal_reasons))  # fmt: skip

    # Row 8: unknown plate, optional alert (decision D-01)
    if not d.registered and not ij and d.flag_unregistered:
        reasons.append(ReasonCode.FLAG_UNREGISTERED)
        alerts.append(
            AlertSpec(
                AlertType.UNREGISTERED_VEHICLE,
                Severity.MEDIUM,
                None,
                (ReasonCode.UNKNOWN_PLATE, ReasonCode.FLAG_UNREGISTERED),
            )
        )

    # FR-PLT-08: near-miss of an active report -> officer review, never an alert
    review = bool(d.possible_match_plates) and not d.reports
    if review:
        reasons.append(ReasonCode.POSSIBLE_MATCH)

    return Decision(
        outcome=_outcome(alerts, review, d.registered),
        reason_codes=tuple(reasons),
        alerts=tuple(alerts),
        reports_to_detect=tuple(detect),
        review_item=review,
        # Safety rule 1: possible matches never feed clone analysis
        use_for_clone_analysis=not review,
    )


_SIGNAL_CODES = frozenset(
    {
        ReasonCode.IMPOSSIBLE_JOURNEY,
        ReasonCode.SIGHTING_APPEARANCE_MISMATCH,
        ReasonCode.REGISTRY_APPEARANCE_MISMATCH,
    }
)

# The sighting gets one outcome: the most serious alert, else review/unknown/pass
_OUTCOME_ORDER = (
    (AlertType.STOLEN_VEHICLE, SightingOutcome.STOLEN_MATCH),
    (AlertType.MISSING_VEHICLE, SightingOutcome.MISSING_MATCH),
    (AlertType.SUSPECTED_CLONE, SightingOutcome.SUSPECTED_CLONE),
    (AlertType.APPEARANCE_MISMATCH, SightingOutcome.APPEARANCE_MISMATCH),
)


def _outcome(alerts: list[AlertSpec], review: bool, registered: bool):
    types = {a.alert_type for a in alerts}
    for alert_type, outcome in _OUTCOME_ORDER:
        if alert_type in types:
            return outcome
    if review:
        return SightingOutcome.POSSIBLE_MATCH
    if not registered:
        return SightingOutcome.UNKNOWN_PLATE
    return SightingOutcome.PASS  # row 7
