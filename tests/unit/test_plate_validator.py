"""Plate validation (FR-PLT-05) and multi-frame voting (FR-PLT-06/07)."""

import pytest

from app.pipeline.plate_validator import PlateValidator, PlateVoter, VoteStatus

validator = PlateValidator()


# Raw OCR text (many taken from real reads of the test photos) -> expected plate
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("KA19AB1234", "KA19AB1234"),
        ("ka 19 ab 1234", "KA19AB1234"),  # lower case and spaces
        ("KA-19-AB-1234", "KA19AB1234"),  # hyphens
        ("INDKA19AB1234", "KA19AB1234"),  # blue IND strip read first
        ("KA24PQ1122IND", "KA24PQ1122"),  # IND strip read last
        ("INDKA19TROOO1", "KA19TR0001"),  # O read instead of 0 in digit slots
        ("INDKAZOEF2468", "KA20EF2468"),  # Z and O in the RTO digits
        ("KAT9HINDP5739", "KA19HP5739"),  # T for 1, IND between the rows
        ("KLIZMP5537", "KL12MP5537"),  # I and Z in the RTO digits
        ("KA19A81234", "KA19AB1234"),  # 8 in a letter slot -> B
        ("TN1801868", "TN18O1868"),  # 9-character plate, 0 in letter slot
        ("22BH1234AA", "22BH1234AA"),  # BH series
        ("XX22BH1234AAYY", "22BH1234AA"),  # BH series inside noise
        ("INLKA20Z6020HVWNDAI", "KA20Z6020"),  # plate inside noisy text
    ],
)
def test_valid_plates_are_corrected(raw, expected):
    assert validator.validate(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "HR98",  # too short (only the top row was read)
        "62310",
        "ZZ19AB1234",  # not a state code
        "KA1AB1234",  # RTO must have two digits
        "KAAB12345",  # no RTO digits at all
        "HADIRD",
    ],
)
def test_invalid_text_is_rejected_not_guessed(raw):
    assert validator.validate(raw) is None


def test_is_valid_checks_state_code():
    assert validator.is_valid("KA19AB1234")
    assert not validator.is_valid("ON19AB1234")


# ---------------------------------------------------------------- voting


def make_voter():
    return PlateVoter(window=10, conf_gate=0.70, timeout_s=10)


def feed(voter, readings, start=0.0, step=0.2):
    """Feed (plate, conf) readings; return the first non-WAITING result."""
    result = None
    for i, (plate, conf) in enumerate(readings):
        result = voter.add(plate, conf, start + i * step)
        if result.status != VoteStatus.WAITING:
            return result
    return result


def test_accepts_after_majority_of_window():
    result = feed(make_voter(), [("KA19AB1234", 0.9)] * 10)
    assert result.status == VoteStatus.ACCEPTED
    assert result.plate == "KA19AB1234"
    assert result.votes == 6  # 6 of 10 is the first majority
    assert result.frames == 6


def test_single_misread_never_wins():
    readings = [("KA19AB1234", 0.9), ("KA19AB1284", 0.95)] * 2 + [
        ("KA19AB1234", 0.9)
    ] * 6
    result = feed(make_voter(), readings)
    assert result.plate == "KA19AB1234"


def test_frames_without_a_plate_count_against_the_majority():
    readings = [("KA19AB1234", 0.9), (None, 0.0)] * 5  # only 5 of 10
    result = feed(make_voter(), readings)
    assert result.status == VoteStatus.WAITING


def test_low_confidence_majority_is_not_accepted():
    voter = make_voter()
    result = feed(voter, [("KA19AB1234", 0.5)] * 10)
    assert result.status == VoteStatus.WAITING
    timeout = voter.add("KA19AB1234", 0.5, now=11.0)
    assert timeout.status == VoteStatus.LOW_CONFIDENCE
    assert timeout.plate is None


def test_no_plate_after_timeout():
    voter = make_voter()
    assert voter.add(None, 0.0, now=0.0).status == VoteStatus.WAITING
    assert voter.add(None, 0.0, now=9.9).status == VoteStatus.WAITING
    result = voter.add(None, 0.0, now=10.0)
    assert result.status == VoteStatus.NO_PLATE
    assert result.plate is None


def test_voter_resets_after_a_decision():
    voter = make_voter()
    feed(voter, [("KA19AB1234", 0.9)] * 6)
    result = feed(voter, [("KA20EF2468", 0.9)] * 6, start=20.0)
    assert result.plate == "KA20EF2468"


def test_defaults_come_from_settings_yaml():
    voter = PlateVoter()
    assert (voter.window, voter.conf_gate, voter.timeout_s) == (10, 0.70, 10)
