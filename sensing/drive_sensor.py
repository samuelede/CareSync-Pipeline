"""
Senses the six expected weekly files against a one-hour arrival SLA.

Usage:
    python -m sensing.drive_sensor --run-id 2026-08-10 --scheduled-at "2026-08-10T06:00:00+00:00"

Three modes, chosen automatically based on what's configured in .env:
    - Service account mode: if GDRIVE_FOLDER_ID + GDRIVE_SERVICE_ACCOUNT_JSON
      (a downloaded key file) are set, authenticates as the service account.
      Some Google Cloud projects have service account key creation blocked
      by an organization policy (iam.disableServiceAccountKeyCreation),
      see docs/google_drive_setup.md for the fix or the OAuth alternative
      below.
    - OAuth mode: if GDRIVE_FOLDER_ID + GDRIVE_OAUTH_CLIENT_SECRET_JSON are
      set instead, authenticates as your own Google account via a one-time
      browser consent screen. No service account key needed at all. The
      resulting token is cached at GDRIVE_OAUTH_TOKEN_JSON and refreshed
      automatically after that.
    - Local-simulation mode: if neither is configured, treats files already
      present in data/landing/<run_id>/ (e.g. from
      scripts.simulate_weekly_drop) as "arrived", and checks their
      filesystem mtime against the SLA window. This is what lets the
      1-hour SLA logic be built, tested, and demoed without a live Drive
      connection.

For each dataset not found within FILE_ARRIVAL_SLA_MINUTES of
scheduled_at: fires an SLA_MISSED Slack + email alert and writes a
SENSING/SLA_MISSED row to the audit trail. Datasets found in time get a
SENSING/ON_TIME audit row.
"""
import argparse
import fnmatch
import os
from datetime import datetime, timedelta, timezone

import yaml

from config.settings import (
    GDRIVE_FOLDER_ID, GDRIVE_SERVICE_ACCOUNT_JSON,
    GDRIVE_OAUTH_CLIENT_SECRET_JSON, GDRIVE_OAUTH_TOKEN_JSON,
    FILE_ARRIVAL_SLA_MINUTES,
)
from notifications.slack_notify import send_slack_alert
from notifications.email_notify import send_email_alert
from scripts.audit_log import write_audit_row

MANIFEST_PATH = "config/file_manifest.yml"
DRIVE_READONLY_SCOPE = ["https://www.googleapis.com/auth/drive.readonly"]


def load_file_manifest() -> list:
    with open(MANIFEST_PATH) as f:
        return yaml.safe_load(f)["files"]


def _auth_mode() -> str:
    """Returns 'service_account', 'oauth', or 'local' based on what's
    configured in .env. Checked in this order because a service account is
    the more automation-friendly path when it's available."""
    if not GDRIVE_FOLDER_ID:
        return "local"
    if os.path.exists(GDRIVE_SERVICE_ACCOUNT_JSON):
        return "service_account"
    if os.path.exists(GDRIVE_OAUTH_CLIENT_SECRET_JSON):
        return "oauth"
    return "local"


def _drive_configured() -> bool:
    return _auth_mode() != "local"


def _build_drive_client_service_account():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        GDRIVE_SERVICE_ACCOUNT_JSON, scopes=DRIVE_READONLY_SCOPE,
    )
    return build("drive", "v3", credentials=creds)


def _build_drive_client_oauth():
    """Authenticates as your own Google account instead of a service
    account, sidestepping any organization policy that blocks service
    account key creation. First run opens a browser consent screen; the
    resulting token is cached at GDRIVE_OAUTH_TOKEN_JSON (gitignored) and
    silently refreshed on every run after that."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(GDRIVE_OAUTH_TOKEN_JSON):
        creds = Credentials.from_authorized_user_file(GDRIVE_OAUTH_TOKEN_JSON, DRIVE_READONLY_SCOPE)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                GDRIVE_OAUTH_CLIENT_SECRET_JSON, DRIVE_READONLY_SCOPE,
            )
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(GDRIVE_OAUTH_TOKEN_JSON) or ".", exist_ok=True)
        with open(GDRIVE_OAUTH_TOKEN_JSON, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


def _build_drive_client():
    mode = _auth_mode()
    if mode == "service_account":
        return _build_drive_client_service_account()
    if mode == "oauth":
        return _build_drive_client_oauth()
    raise RuntimeError("Drive not configured, this should only be called when _drive_configured() is True")


def sense_live(dataset: str, pattern: str, run_id: str):
    """Lists the Drive folder for a matching file and downloads it. Returns
    (arrived: bool, arrived_at: datetime | None)."""
    import io
    from googleapiclient.http import MediaIoBaseDownload

    service = _build_drive_client()
    query = f"'{GDRIVE_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, createdTime)").execute()
    candidates = [f for f in results.get("files", []) if fnmatch.fnmatch(f["name"], pattern)]

    if not candidates:
        return False, None

    file_meta = candidates[0]
    out_dir = f"data/landing/{run_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/{dataset}.csv"

    request = service.files().get_media(fileId=file_meta["id"])
    with io.FileIO(out_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    arrived_at = datetime.fromisoformat(file_meta["createdTime"].replace("Z", "+00:00"))
    return True, arrived_at


def sense_local(dataset: str, run_id: str):
    """Local-simulation fallback: checks data/landing/<run_id>/<dataset>.csv
    on disk and uses its file mtime as the arrival time."""
    path = f"data/landing/{run_id}/{dataset}.csv"
    if not os.path.exists(path):
        return False, None
    arrived_at = datetime.fromtimestamp(os.path.getmtime(path), tz=timezone.utc)
    return True, arrived_at


def main(run_id: str, scheduled_at: str = None):
    manifest = load_file_manifest()
    scheduled_dt = (
        datetime.fromisoformat(scheduled_at) if scheduled_at
        else datetime.now(timezone.utc) - timedelta(minutes=1)  # default: "just now" for local runs
    )
    sla_deadline = scheduled_dt + timedelta(minutes=FILE_ARRIVAL_SLA_MINUTES)
    live = _drive_configured()

    results = {}
    for entry in manifest:
        dataset, pattern = entry["dataset"], entry["pattern"]
        if live:
            arrived, arrived_at = sense_live(dataset, pattern, run_id)
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

    print(f"[drive_sensor] run {run_id} ({_auth_mode()}): {results}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scheduled-at", default=None,
                         help="ISO timestamp the files were due, e.g. 2026-08-10T06:00:00+00:00")
    args = parser.parse_args()
    main(args.run_id, args.scheduled_at)
