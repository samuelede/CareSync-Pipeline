"""
Sends CareSync alerts via email as the second channel alongside Slack
(spec requires both, not either/or).

Two providers, selected by EMAIL_PROVIDER in .env:
    resend (default)  simplest setup, no app passwords, a single API key.
    smtp               any standard SMTP server (Gmail app password,
                        Amazon SES, SendGrid's SMTP interface).

Setup:
    Resend: set RESEND_API_KEY and RESEND_FROM_EMAIL in .env. See
    docs/notification_matrix.md for the two-minute setup.
    SMTP: set SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD instead,
    and set EMAIL_PROVIDER=smtp.

Usage:
    from notifications.email_notify import send_email_alert
    send_email_alert(event="RUN_SUCCESS", run_id="2026-08-10", detail={...})

Mirrors the same event matrix and message content as slack_notify.py so
both channels always agree on what happened.
"""
import smtplib
from email.mime.text import MIMEText

from config.settings import (
    EMAIL_PROVIDER, RESEND_API_KEY, RESEND_FROM_EMAIL,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL_TO,
)


def format_body(event: str, run_id: str, detail: dict) -> str:
    lines = [f"CareSync: {event}", f"Run ID: {run_id}", ""]
    lines += [f"{k}: {v}" for k, v in detail.items()]
    return "\n".join(lines)


def _send_via_resend(subject: str, body: str):
    import resend
    resend.api_key = RESEND_API_KEY
    resend.Emails.send({
        "from": RESEND_FROM_EMAIL,
        "to": [NOTIFY_EMAIL_TO],
        "subject": subject,
        "text": body,
    })


def _send_via_smtp(subject: str, body: str):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_EMAIL_TO

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, [NOTIFY_EMAIL_TO], msg.as_string())


def _email_configured() -> bool:
    if EMAIL_PROVIDER == "resend":
        return bool(RESEND_API_KEY)
    return bool(SMTP_HOST and SMTP_USER)


def send_email_alert(event: str, run_id: str, detail: dict):
    body = format_body(event, run_id, detail)
    subject = f"[CareSync] {event} (run {run_id})"

    if not _email_configured():
        print(f"[email_notify] {EMAIL_PROVIDER} not configured. Would have sent:\n{body}")
        return

    try:
        if EMAIL_PROVIDER == "resend":
            _send_via_resend(subject, body)
        else:
            _send_via_smtp(subject, body)
    except Exception as e:
        print(f"[email_notify] failed to send via {EMAIL_PROVIDER}: {e}")
