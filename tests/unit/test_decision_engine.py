"""Table-driven tests for every row of the PRD §5 decision matrix (task 3.3)."""

from dataclasses import replace

import pytest

from app.domain.decision_engine import DecisionInput, ReportMatch, decide
from app.domain.states import (
    AlertType,
    ReasonCode,
    RecoveryStatus,
    ReportType,
    Severity,
    SightingOutcome,
)

STOLEN = ReportMatch("r-stolen", ReportType.STOLEN, RecoveryStatus.REPORTED)
STOLEN_DETECTED = ReportMatch("r-stolen2", ReportType.STOLEN, RecoveryStatus.DETECTED)
MISSING = ReportMatch("r-missing", ReportType.MISSING, RecoveryStatus.REPORTED)

OK = DecisionInput(read_status="ACCEPTED", plate="KA19AB1234", registered=True)
UNKNOWN = replace(OK, registered=False)


def alerts_of(decision):
    return [(a.alert_type, a.severity) for a in decision.alerts]


# (name, input, expected outcome, expected alerts [(type, severity)])
MATRIX = [
    ("row1 no plate", DecisionInput("NO_PLATE"), SightingOutcome.NO_PLATE, []),
    ("row1 accepted but empty", DecisionInput("ACCEPTED", plate=None),
     SightingOutcome.NO_PLATE, []),
    ("row1 low confidence", DecisionInput("LOW_CONFIDENCE"),
     SightingOutcome.LOW_CONFIDENCE, []),
    ("row2 stolen", replace(OK, reports=(STOLEN,)), SightingOutcome.STOLEN_MATCH,
     [(AlertType.STOLEN_VEHICLE, Severity.HIGH)]),
    ("row3 missing", replace(OK, reports=(MISSING,)), SightingOutcome.MISSING_MATCH,
     [(AlertType.MISSING_VEHICLE, Severity.HIGH)]),
    ("row4 IJ + AM", replace(OK, impossible_journey=True, sighting_mismatch=True),
     SightingOutcome.SUSPECTED_CLONE, [(AlertType.SUSPECTED_CLONE, Severity.HIGH)]),
    ("row4 IJ + RM", replace(OK, impossible_journey=True, registry_mismatch=True),
     SightingOutcome.SUSPECTED_CLONE, [(AlertType.SUSPECTED_CLONE, Severity.HIGH)]),
    ("row5 IJ only", replace(OK, impossible_journey=True),
     SightingOutcome.SUSPECTED_CLONE, [(AlertType.SUSPECTED_CLONE, Severity.MEDIUM)]),
    ("row6 AM only", replace(OK, sighting_mismatch=True),
     SightingOutcome.APPEARANCE_MISMATCH, [(AlertType.APPEARANCE_MISMATCH, Severity.LOW)]),
    ("row6 RM only", replace(OK, registry_mismatch=True),
     SightingOutcome.APPEARANCE_MISMATCH, [(AlertType.APPEARANCE_MISMATCH, Severity.LOW)]),
    ("row7 pass", OK, SightingOutcome.PASS, []),
    ("row8 unknown, flag off", UNKNOWN, SightingOutcome.UNKNOWN_PLATE, []),
    ("row8 unknown, flag on", replace(UNKNOWN, flag_unregistered=True),
     SightingOutcome.UNKNOWN_PLATE, [(AlertType.UNREGISTERED_VEHICLE, Severity.MEDIUM)]),
    ("row8 + IJ uses AM only (RM ignored)",
     replace(UNKNOWN, impossible_journey=True, registry_mismatch=True),
     SightingOutcome.SUSPECTED_CLONE, [(AlertType.SUSPECTED_CLONE, Severity.MEDIUM)]),
    ("row8 + IJ + AM", replace(UNKNOWN, impossible_journey=True, sighting_mismatch=True),
     SightingOutcome.SUSPECTED_CLONE, [(AlertType.SUSPECTED_CLONE, Severity.HIGH)]),
    ("row8 + IJ, flag on: clone alert, no unregistered alert",
     replace(UNKNOWN, impossible_journey=True, flag_unregistered=True),
     SightingOutcome.SUSPECTED_CLONE, [(AlertType.SUSPECTED_CLONE, Severity.MEDIUM)]),
    ("stolen + IJ raises two alerts", replace(OK, reports=(STOLEN,), impossible_journey=True),
     SightingOutcome.STOLEN_MATCH,
     [(AlertType.STOLEN_VEHICLE, Severity.HIGH), (AlertType.SUSPECTED_CLONE, Severity.MEDIUM)]),
    ("stolen + missing", replace(OK, reports=(STOLEN, MISSING)), SightingOutcome.STOLEN_MATCH,
     [(AlertType.STOLEN_VEHICLE, Severity.HIGH), (AlertType.MISSING_VEHICLE, Severity.HIGH)]),
    ("possible match (S10)", replace(UNKNOWN, possible_match_plates=("KA21GH1357",)),
     SightingOutcome.POSSIBLE_MATCH, []),
]  # fmt: skip


@pytest.mark.parametrize(
    ("given", "outcome", "alerts"),
    [m[1:] for m in MATRIX],
    ids=[m[0] for m in MATRIX],
)
def test_decision_matrix(given, outcome, alerts):
    decision = decide(given)
    assert decision.outcome == outcome
    assert alerts_of(decision) == alerts


def test_same_input_gives_same_decision():  # PRD §5 safety rule 3
    given = replace(OK, reports=(STOLEN,), impossible_journey=True)
    assert decide(given) == decide(given)


def test_reported_report_moves_to_detected_but_detected_stays():
    decision = decide(replace(OK, reports=(STOLEN, STOLEN_DETECTED)))
    assert decision.reports_to_detect == ("r-stolen",)
    assert [a.report_id for a in decision.alerts] == ["r-stolen", "r-stolen2"]


def test_stolen_with_registry_mismatch_keeps_high_and_adds_reason():
    decision = decide(replace(OK, reports=(STOLEN,), registry_mismatch=True))
    stolen = decision.alerts[0]
    assert (stolen.alert_type, stolen.severity) == (
        AlertType.STOLEN_VEHICLE,
        Severity.HIGH,
    )
    assert ReasonCode.APPEARANCE_MISMATCH in stolen.reason_codes
    # RM without IJ also raises the LOW appearance alert (row 6)
    assert alerts_of(decision)[1] == (AlertType.APPEARANCE_MISMATCH, Severity.LOW)


def test_email_only_for_high_and_medium():
    decision = decide(replace(OK, reports=(STOLEN,), sighting_mismatch=True))
    assert [a.email for a in decision.alerts] == [True, False]


def test_reason_codes_explain_the_outcome():
    decision = decide(replace(OK, impossible_journey=True, sighting_mismatch=True))
    assert decision.reason_codes == (
        ReasonCode.REGISTERED,
        ReasonCode.IMPOSSIBLE_JOURNEY,
        ReasonCode.SIGHTING_APPEARANCE_MISMATCH,
    )
    assert decision.alerts[0].reason_codes == decision.reason_codes[1:]


@pytest.mark.parametrize(
    "given",
    [
        DecisionInput("NO_PLATE"),
        DecisionInput("LOW_CONFIDENCE"),
        replace(UNKNOWN, possible_match_plates=("KA21GH1357",)),
    ],
    ids=["no plate", "low confidence", "possible match"],
)
def test_unreliable_reads_never_feed_clone_analysis(given):  # safety rule 1
    decision = decide(given)
    assert decision.use_for_clone_analysis is False
    assert decision.alerts == ()


def test_possible_match_is_ignored_when_plate_matches_exactly():
    decision = decide(replace(OK, reports=(STOLEN,), possible_match_plates=("X",)))
    assert decision.review_item is False
    assert decision.use_for_clone_analysis is True
