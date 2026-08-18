"""
Sends CareSync alerts via SMTP email as the second channel alongside Slack
(spec requires both, not either/or).

Setup:
    Set SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / NOTIFY_EMAIL_TO
    in .env. Works with any standard SMTP provider (e.g. a Gmail app
    password, SendGrid, Amazon SES SMTP interface).

Usage:
    from notifications.email_notify import send_email_alert
    send_email_alert(event="RUN_SUCCESS", run_id="2026-08-10", detail={...})

Mirrors the same event matrix and message content as slack_notify.py so
both channels always agree on what happened.
"""
import smtplib
from email.mime.text import MIMEText
from config.settings import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL_TO


def format_body(event: str, run_id: str, detail: dict) -> str:
    lines = [f"CareSync: {event}", f"Run ID: {run_id}", ""]
    lines += [f"{k}: {v}" for k, v in detail.items()]
    return "\n".join(lines)


def send_email_alert(event: str, run_id: str, detail: dict):
    body = format_body(event, run_id, detail)
    if not SMTP_HOST or not SMTP_USER:
        print(f"[email_notify] SMTP not configured. Would have sent:\n{body}")
        return
    msg = MIMEText(body)
    msg["Subject"] = f"[CareSync] {event} (run {run_id})"
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [NOTIFY_EMAIL_TO], msg.as_string())
    except Exception as e:
        print(f"[email_notify] failed to send: {e}")
