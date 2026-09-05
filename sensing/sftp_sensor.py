"""
Senses the six expected weekly files against a one-hour arrival SLA, over
SFTP. This is the Week 3 production landing zone, replacing Google Drive
without changing anything downstream: pre_validate.py, the loader, and
dbt all read from data/landing/<run_id>/ exactly the same way regardless
of whether sensing/drive_sensor.py or this module put the files there.

Usage:
    python -m sensing.sftp_sensor --run-id 2026-08-10 --scheduled-at "2026-08-10T06:00:00+00:00"

Configured via .env (see .env.example): SFTP_HOST, SFTP_USER, and either
SFTP_PASSWORD or SFTP_KEY_PATH (key-based auth preferred, same reasoning
as Snowflake's key-pair auth elsewhere in this project, no password to
rotate or leak). Falls back to local-simulation mode automatically if
SFTP_HOST is unset, exactly like drive_sensor.py falls back when Drive
isn't configured, so this can be built and tested without a live SFTP
server, then pointed at one for production with no code changes.
"""
import argparse
import fnmatch
import os
import stat
from datetime import datetime, timedelta, timezone

import yaml

from config.settings import (
    SFTP_HOST, SFTP_PORT, SFTP_USER, SFTP_PASSWORD, SFTP_KEY_PATH,
    FILE_ARRIVAL_SLA_MINUTES,
)
from notifications.slack_notify import send_slack_alert
from notifications.email_notify import send_email_alert
from scripts.audit_log import write_audit_row

MANIFEST_PATH = "config/file_manifest.yml"


def load_file_manifest() -> list:
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f)["files"]


def _sftp_configured() -> bool:
    return bool(SFTP_HOST)


def _connect_sftp():
    import paramiko
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    if SFTP_KEY_PATH and os.path.exists(SFTP_KEY_PATH):
        key = paramiko.RSAKey.from_private_key_file(SFTP_KEY_PATH)
        transport.connect(username=SFTP_USER, pkey=key)
    else:
        transport.connect(username=SFTP_USER, password=SFTP_PASSWORD)
    return paramiko.SFTPClient.from_transport(transport), transport


def sense_live_sftp(sftp, dataset: str, pattern: str, run_id: str, remote_dir: str = "."):
    """Lists the SFTP directory for a matching file and downloads it.
    Returns (arrived: bool, arrived_at: datetime | None)."""
    entries = sftp.listdir_attr(remote_dir)
    candidates = [e for e in entries if fnmatch.fnmatch(e.filename, pattern) and not stat.S_ISDIR(e.st_mode)]
    if not candidates:
        return False, None

    entry = max(candidates, key=lambda e: e.st_mtime)
    out_dir = f"data/landing/{run_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/{dataset}.csv"
    sftp.get(f"{remote_dir}/{entry.filename}", out_path)

    arrived_at = datetime.fromtimestamp(entry.st_mtime, tz=timezone.utc)
    return True, arrived_at


def sense_local(dataset: str, run_id: str):
    """Local-simulation fallback, identical contract to drive_sensor.py's
    version: checks data/landing/<run_id>/<dataset>.csv on disk and uses
    its file mtime as the arrival time."""
    path = f"data/landing/{run_id}/{dataset}.csv"
    if not os.path.exists(path):
        return False, None
    arrived_at = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    return True, arrived_at


def main(run_id: str, scheduled_at: str = None):
    manifest = load_file_manifest()
    scheduled_dt = (
        datetime.fromisoformat(scheduled_at) if scheduled_at
        else datetime.now(timezone.utc) - timedelta(minutes=1)
    )
    sla_deadline = scheduled_dt + timedelta(minutes=FILE_ARRIVAL_SLA_MINUTES)
    live = _sftp_configured()

    sftp = transport = None
    if live:
        sftp, transport = _connect_sftp()

    results = {}
    try:
        for entry in manifest:
            dataset, pattern = entry["dataset"], entry["pattern"]
            if live:
                arrived, arrived_at = sense_live_sftp(sftp, dataset, pattern, run_id)
            else:
                arrived, arrived_at = sense_local(dataset, run_id)

            if not arrived:
                results[dataset] = "SLA_MISSED"
                write_audit_row(run_id=run_id, dataset=dataset, stage="SENSING", status="SLA_MISSED")
                detail = {"dataset": dataset, "scheduled_at": scheduled_dt.isoformat(),
                          "sla_deadline": sla_deadline.isoformat()}
                send_slack_alert("SLA_MISSED", run_id, detail)
                send_email_alert("SLA_MISSED", run_id, detail)
                continue

            on_time = arrived_at <= sla_deadline
            status = "ON_TIME" if on_time else "SLA_MISSED"
            results[dataset] = status
            write_audit_row(run_id=run_id, dataset=dataset, stage="SENSING", status=status)

            if not on_time:
                detail = {"dataset": dataset, "arrived_at": arrived_at.isoformat(),
                          "sla_deadline": sla_deadline.isoformat()}
                send_slack_alert("SLA_MISSED", run_id, detail)
                send_email_alert("SLA_MISSED", run_id, detail)
    finally:
        if transport:
            transport.close()

    print(f"[sftp_sensor] run {run_id} ({'live SFTP' if live else 'local simulation'}): {results}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scheduled-at", default=None)
    args = parser.parse_args()
    main(args.run_id, args.scheduled_at)
