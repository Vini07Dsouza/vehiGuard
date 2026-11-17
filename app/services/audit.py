"""Append-only audit log with a hash chain (FR-LOG, architecture §7.2).

Each entry stores hash = SHA-256(prev_hash + record). Changing or deleting
an old entry breaks the chain, which verify_chain() reports. The database
also refuses UPDATE and DELETE on this table (see the migration).
"""

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import AuditLog

# Any fixed number: makes concurrent appends wait for each other
_AUDIT_LOCK_ID = 7_202_611


def _record_hash(prev_hash: str | None, entry: AuditLog) -> str:
    record = {
        "user_id": entry.user_id,
        "action": entry.action,
        "entity": entry.entity,
        "entity_id": entry.entity_id,
        "details": entry.details,
        # UTC, because PostgreSQL returns timestamps in the session time zone
        "ts": entry.ts.astimezone(UTC).isoformat(),
    }
    payload = (prev_hash or "") + json.dumps(record, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def append_audit(
    session: Session,
    action: str,
    entity: str,
    entity_id: str | None = None,
    details: dict | None = None,
    user_id: str | None = None,
) -> AuditLog:
    """Add one audit entry. The caller commits the session."""
    if session.bind.dialect.name == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:id)"), {"id": _AUDIT_LOCK_ID}
        )
    prev_hash = session.scalar(
        select(AuditLog.hash).order_by(AuditLog.seq.desc()).limit(1)
    )
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=details or {},
        ts=datetime.now(UTC),
        prev_hash=prev_hash,
    )
    entry.hash = _record_hash(prev_hash, entry)
    session.add(entry)
    session.flush()
    return entry


def verify_chain(session: Session) -> tuple[bool, str | None]:
    """Return (True, None) if the chain is intact, else (False, broken log_id)."""
    prev_hash = None
    for entry in session.scalars(select(AuditLog).order_by(AuditLog.seq)):
        if entry.prev_hash != prev_hash or entry.hash != _record_hash(prev_hash, entry):
            return False, entry.log_id
        prev_hash = entry.hash
    return True, None
