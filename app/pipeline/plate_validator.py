"""Turn raw OCR text into a valid Indian plate, and vote across frames.

FR-PLT-05: normalise, fix letter/digit mix-ups by position, validate.
           Invalid text is rejected (None), never guessed.
FR-PLT-06: accept a plate only when it wins a majority of the last N frames
           and its mean confidence passes the gate.
FR-PLT-07: nothing accepted within the timeout -> NO_PLATE (no alert).

Rules come from config/plate_patterns.yaml; N, gate and timeout from
config/settings.yaml (pipeline section).
"""

import re
from collections import Counter, deque
from dataclasses import dataclass
from enum import StrEnum

from app.core.config import load_yaml

# Plate lengths to try, most common first: KA19AB1234, KA19A1234, KA19ABC1234
STANDARD_LENGTHS = (10, 9, 11)


@dataclass(frozen=True)
class PlateRules:
    standard: re.Pattern
    bh_series: re.Pattern
    state_codes: frozenset[str]
    to_digit: dict[str, str]
    to_letter: dict[str, str]
    ignore_text: tuple[str, ...]

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "PlateRules":
        cfg = cfg or load_yaml("plate_patterns.yaml")
        return cls(
            standard=re.compile(cfg["patterns"]["standard"]),
            bh_series=re.compile(cfg["patterns"]["bh_series"]),
            state_codes=frozenset(cfg["state_codes"]),
            to_digit={str(k): str(v) for k, v in cfg["to_digit"].items()},
            to_letter={str(k): str(v) for k, v in cfg["to_letter"].items()},
            ignore_text=tuple(cfg.get("ignore_text", [])),
        )


class PlateValidator:
    def __init__(self, rules: PlateRules | None = None):
        self.rules = rules or PlateRules.from_config()
        # BH search pattern: the configured full-match pattern without ^ and $
        self._bh_search = re.compile(self.rules.bh_series.pattern.strip("^$"))

    def normalise(self, text: str) -> str:
        """Uppercase and keep only A-Z and 0-9."""
        return re.sub(r"[^A-Z0-9]", "", text.upper())

    def _remove_ignored(self, text: str) -> str:
        for word in self.rules.ignore_text:
            # "IND" is often read with its first letter missing or wrong
            text = re.sub(rf"^[A-Z0-9]?{word[1:]}", "", text) if word else text
            text = text.replace(word, "")
        return text

    def _fix_positions(self, chunk: str) -> str:
        """Letters in the state and series slots, digits everywhere else."""
        n = len(chunk)
        out = []
        for i, ch in enumerate(chunk):
            letter_slot = i < 2 or 4 <= i < n - 4
            table = self.rules.to_letter if letter_slot else self.rules.to_digit
            out.append(table.get(ch, ch))
        return "".join(out)

    def is_valid(self, plate: str) -> bool:
        if self.rules.bh_series.match(plate):
            return True
        return bool(self.rules.standard.match(plate)) and (
            plate[:2] in self.rules.state_codes
        )

    def validate(self, raw_text: str) -> str | None:
        """Return the corrected plate, or None if the text is not a valid plate."""
        text = self._remove_ignored(self.normalise(raw_text))
        bh = self._bh_search.search(text)
        if bh:
            return bh.group(0)
        for n in STANDARD_LENGTHS:
            for start in range(len(text) - n + 1):
                candidate = self._fix_positions(text[start : start + n])
                if self.is_valid(candidate):
                    return candidate
        return None


class VoteStatus(StrEnum):
    WAITING = "WAITING"  # keep reading frames
    ACCEPTED = "ACCEPTED"
    NO_PLATE = "NO_PLATE"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


@dataclass(frozen=True)
class VoteResult:
    status: VoteStatus
    plate: str | None = None
    confidence: float | None = None
    votes: int = 0
    frames: int = 0


class PlateVoter:
    """Collects one reading per frame for one vehicle and decides when to accept.

    Call add() for every processed frame (plate=None when nothing valid was
    read). After ACCEPTED, NO_PLATE or LOW_CONFIDENCE the voter resets itself.
    """

    def __init__(
        self,
        window: int | None = None,
        conf_gate: float | None = None,
        timeout_s: float | None = None,
    ):
        cfg = load_yaml("settings.yaml")["pipeline"]
        self.window = window or cfg["plate_vote_frames"]
        self.conf_gate = cfg["ocr_conf_gate"] if conf_gate is None else conf_gate
        self.timeout_s = timeout_s or cfg["plate_timeout_s"]
        self.reset()

    def reset(self) -> None:
        self._readings: deque[tuple[str | None, float]] = deque(maxlen=self.window)
        self._started_at: float | None = None
        self._frames = 0
        self._saw_low_confidence = False

    def add(self, plate: str | None, confidence: float, now: float) -> VoteResult:
        if self._started_at is None:
            self._started_at = now
        self._frames += 1
        self._readings.append((plate, confidence if plate else 0.0))

        counts = Counter(p for p, _ in self._readings if p)
        if counts:
            leader, votes = counts.most_common(1)[0]
            if votes > self.window / 2:  # majority of the window
                confs = [c for p, c in self._readings if p == leader]
                mean_conf = sum(confs) / len(confs)
                if mean_conf >= self.conf_gate:
                    return self._finish(
                        VoteStatus.ACCEPTED, leader, round(mean_conf, 3), votes
                    )
                self._saw_low_confidence = True

        if now - self._started_at >= self.timeout_s:
            status = (
                VoteStatus.LOW_CONFIDENCE
                if self._saw_low_confidence
                else VoteStatus.NO_PLATE
            )
            return self._finish(status)
        return VoteResult(VoteStatus.WAITING, frames=self._frames)

    def _finish(self, status, plate=None, confidence=None, votes=0) -> VoteResult:
        result = VoteResult(status, plate, confidence, votes, self._frames)
        self.reset()
        return result
