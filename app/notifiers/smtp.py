"""Email alerts over SMTP with TLS (FR-ALR-03). Used when ALERT_MODE=live.

Settings come from .env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
SMTP_FROM. For Gmail, use an App Password, not your normal password.
"""

import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings
from app.notifiers import NotifierError

TIMEOUT_S = 15


def format_email(target: str, payload: dict, sender: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = target
    msg["Subject"] = (
        f"[VehiGuard {payload['severity']}] {payload['type']} - {payload['plate']}"
    )
    camera = payload["camera"]
    lines = [
        f"Alert: {payload['type']} ({payload['severity']})",
        f"Plate: {payload['plate']}",
        (
            f"Seen at: {camera['name']} ({camera['id']}), "
            f"{camera['lat']:.5f}, {camera['lon']:.5f}"
        ),
        f"Time: {payload['observed_at']}",
        f"Station: {payload['station']['name']}",
        f"Reasons: {', '.join(payload['reason_codes'])}",
    ]
    if payload.get("report"):
        r = payload["report"]
        lines.append(f"Report: {r['type']} {r['fir_ref']} (now {r['status']})")
    lines.append(f"Evidence files: {len(payload['evidence'])}")
    lines.append(f"Alert ID: {payload['alert_id']}")
    lines.append("")
    lines.append("This alert is a lead, not a verdict. Verify before acting.")
    msg.set_content("\n".join(lines))
    return msg


class SmtpNotifier:
    channel = "EMAIL"

    def send(self, target: str, payload: dict) -> None:
        s = get_settings()
        if not s.smtp_host or not s.smtp_from:
            raise NotifierError("SMTP is not configured in .env")
        msg = format_email(target, payload, s.smtp_from)
        try:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=TIMEOUT_S) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if s.smtp_user:
                    smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
        except (OSError, smtplib.SMTPException) as exc:
            raise NotifierError(f"SMTP delivery failed: {exc}") from exc
