"""Deliver queued alerts with retry and back-off (task 3.6, FR-ALR-04).

    QUEUED -> SENDING -> DELIVERED
                      -> RETRYING (wait 5, 10, 20, 40 ... s) -> SENDING ...
                      -> FAILED after OUTBOX_MAX_ATTEMPTS

A failing channel never blocks detection (NFR-REL-05): delivery runs in its
own scheduler thread. Run it on its own with:  python -m app.services.outbox
"""

import logging
import time
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import load_yaml
from app.db.models import Alert, Outbox
from app.domain.states import OutboxChannel, OutboxStatus
from app.notifiers import NotifierError
from app.notifiers.simulated import SimulatedNotifier
from app.notifiers.smtp import SmtpNotifier
from app.services.alerts import alert_payload
from app.services.audit import append_audit

log = logging.getLogger("vehiguard.outbox")
BASE_DELAY_S = 5
MAX_DELAY_S = 300
POLL_EVERY_S = 5


def retry_delay(attempts: int) -> timedelta:
    """Exponential back-off: 5 s, 10 s, 20 s ... capped at 5 minutes."""
    return timedelta(seconds=min(BASE_DELAY_S * 2 ** max(attempts - 1, 0), MAX_DELAY_S))


def default_notifiers() -> dict:
    return {
        OutboxChannel.SIMULATED: SimulatedNotifier(),
        OutboxChannel.EMAIL: SmtpNotifier(),
    }


def dispatch_due(
    session: Session, now: datetime | None = None, notifiers: dict | None = None
) -> dict[str, int]:
    """Try every message that is due once. The caller commits. Returns counts."""
    now = now or datetime.now(UTC)
    notifiers = notifiers or default_notifiers()
    max_attempts = load_yaml("settings.yaml")["alerts"]["outbox_max_attempts"]
    due = session.scalars(
        select(Outbox)
        .where(
            Outbox.status.in_((OutboxStatus.QUEUED, OutboxStatus.RETRYING)),
            Outbox.next_attempt_at <= now,
        )
        .order_by(Outbox.next_attempt_at)
        .with_for_update(skip_locked=True)  # safe with several workers
    ).all()
    counts = {"delivered": 0, "retrying": 0, "failed": 0}
    for item in due:
        item.status = OutboxStatus.SENDING
        item.attempts += 1
        try:
            payload = alert_payload(session, session.get(Alert, item.alert_id))
            notifiers[item.channel].send(item.target, payload)
        except (NotifierError, KeyError) as exc:
            item.last_error = str(exc)[:500]
            if item.attempts >= max_attempts:
                item.status = OutboxStatus.FAILED
                counts["failed"] += 1
                append_audit(session, "ALERT_DELIVERY_FAILED", "outbox",
                             item.outbox_id, {"error": item.last_error})  # fmt: skip
                log.error("Alert %s delivery FAILED: %s", item.alert_id, exc)
            else:
                item.status = OutboxStatus.RETRYING
                item.next_attempt_at = now + retry_delay(item.attempts)
                counts["retrying"] += 1
                log.warning("Alert %s delivery failed (attempt %s), retrying",
                            item.alert_id, item.attempts)  # fmt: skip
        else:
            item.status = OutboxStatus.DELIVERED
            item.last_error = None
            counts["delivered"] += 1
            log.info("Alert %s delivered to %s (%s)", item.alert_id, item.target,
                     item.channel)  # fmt: skip
    return counts


def start_scheduler(every_s: float = POLL_EVERY_S) -> BackgroundScheduler:
    """Run dispatch_due in a background thread every few seconds."""
    from app.db.session import SessionLocal

    def job():
        try:
            with SessionLocal() as session:
                dispatch_due(session)
                session.commit()
        except Exception:
            log.exception("Outbox run failed")

    def retention_job():
        from app.services.retention import purge_expired

        try:
            with SessionLocal() as session:
                result = purge_expired(session)
                session.commit()
                log.info("Evidence retention: %s", result)
        except Exception:
            log.exception("Evidence retention failed")

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(job, "interval", seconds=every_s, max_instances=1,
                      coalesce=True, next_run_time=datetime.now(UTC))  # fmt: skip
    # FR-ADM-04: purge expired evidence once a day (and once at start-up)
    scheduler.add_job(retention_job, "interval", hours=24, max_instances=1,
                      coalesce=True, next_run_time=datetime.now(UTC))  # fmt: skip
    scheduler.start()
    return scheduler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        datefmt="%H:%M:%S")  # fmt: skip
    log.info("Outbox worker running (Ctrl+C to stop)")
    scheduler = start_scheduler()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
