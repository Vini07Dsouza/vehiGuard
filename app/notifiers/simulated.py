"""Simulated police inbox (FR-ALR-06): the demo works with no external service.

Each delivered alert is appended as one JSON line to
data/inbox/<station email>.jsonl.

To simulate a network outage (scenario S13 / metric M7), create the file
data/inbox/NETWORK_DOWN. While it exists every delivery fails, so alerts wait
in the outbox and retry; delete it and they are delivered.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import ROOT_DIR
from app.notifiers import NotifierError

INBOX_DIR = ROOT_DIR / "data" / "inbox"
OUTAGE_FLAG = "NETWORK_DOWN"


class SimulatedNotifier:
    channel = "SIMULATED"

    def __init__(self, inbox_dir: Path | None = None):
        self.inbox_dir = inbox_dir or INBOX_DIR

    def send(self, target: str, payload: dict) -> None:
        if (self.inbox_dir / OUTAGE_FLAG).exists():
            raise NotifierError("Simulated network outage (NETWORK_DOWN file present)")
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        line = {"delivered_at": datetime.now(UTC).isoformat(), "to": target, **payload}
        safe_name = "".join(c if c.isalnum() or c in "@._-" else "_" for c in target)
        with open(self.inbox_dir / f"{safe_name}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(line, default=str) + "\n")
