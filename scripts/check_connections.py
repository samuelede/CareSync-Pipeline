"""
Checks that every external connection the pipeline depends on is reachable
before you run anything that creates databases, populates data, or touches
a real service. Run this first, every time, before sensing, loading,
dbt, or notifications.

Usage:
    python -m scripts.check_connections
    python -m scripts.check_connections --strict   # exit non-zero on any failure

Checks, in the order the pipeline uses them:
    1. .env file present and loaded
    2. Google Drive (service account key or OAuth token + API reachability)
    3. Snowflake (account/user/password + a real SELECT round trip)
    4. Slack (bot token + auth.test call)
    5. SMTP (host/port reachable + login)

Each check reports one of:
    OK        configured and reachable
    SKIPPED   not configured, pipeline will fall back to local-simulation/dry-run mode
    FAILED    configured but unreachable, fix before proceeding

This intentionally does not import any pipeline module beyond config.settings,
so it can be run standalone with nothing else set up yet.
"""
import argparse
import os
import socket
import sys

from config.settings import (
    GDRIVE_FOLDER_ID, GDRIVE_SERVICE_ACCOUNT_JSON,
    GDRIVE_OAUTH_CLIENT_SECRET_JSON, GDRIVE_OAUTH_TOKEN_JSON,
    GDRIVE_FORCE_LOCAL,
    SNOWFLAKE_CONFIG, get_snowflake_connect_kwargs,
    SLACK_BOT_TOKEN, SLACK_CHANNEL_ID,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
)

OK, SKIPPED, FAILED = "OK", "SKIPPED", "FAILED"
DRIVE_READONLY_SCOPE = ["https://www.googleapis.com/auth/drive.readonly"]


def check_env_file() -> tuple:
    if os.path.exists(".env"):
        return OK, ".env found"
    return FAILED, ".env not found. Run: cp .env.example .env, then fill in every value"


def _check_drive_service_account() -> tuple:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        GDRIVE_SERVICE_ACCOUNT_JSON, scopes=DRIVE_READONLY_SCOPE,
    )
    service = build("drive", "v3", credentials=creds)
    service.files().list(
        q=f"'{GDRIVE_FOLDER_ID}' in parents", pageSize=1, fields="files(id)"
    ).execute()
    return OK, f"folder {GDRIVE_FOLDER_ID} reachable (service account)"


def _check_drive_oauth() -> tuple:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not os.path.exists(GDRIVE_OAUTH_TOKEN_JSON):
        return FAILED, (
            f"{GDRIVE_OAUTH_CLIENT_SECRET_JSON} found but no cached token yet. "
            "Run python -m sensing.drive_sensor once to complete the one-time "
            "browser consent, see docs/google_drive_setup.md"
        )
    creds = Credentials.from_authorized_user_file(GDRIVE_OAUTH_TOKEN_JSON, DRIVE_READONLY_SCOPE)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    service = build("drive", "v3", credentials=creds)
    service.files().list(
        q=f"'{GDRIVE_FOLDER_ID}' in parents", pageSize=1, fields="files(id)"
    ).execute()
    return OK, f"folder {GDRIVE_FOLDER_ID} reachable (OAuth)"


def check_google_drive() -> tuple:
    if GDRIVE_FORCE_LOCAL:
        return SKIPPED, "GDRIVE_FORCE_LOCAL=true; sensing will use local-simulation mode regardless of other Drive settings"
    if not GDRIVE_FOLDER_ID:
        return SKIPPED, "GDRIVE_FOLDER_ID not set in .env; sensing will use local-simulation mode"

    has_service_account = os.path.exists(GDRIVE_SERVICE_ACCOUNT_JSON)
    has_oauth_client = os.path.exists(GDRIVE_OAUTH_CLIENT_SECRET_JSON)

    if not has_service_account and not has_oauth_client:
        return FAILED, (
            f"GDRIVE_FOLDER_ID is set but neither {GDRIVE_SERVICE_ACCOUNT_JSON} "
            f"nor {GDRIVE_OAUTH_CLIENT_SECRET_JSON} exists. See docs/google_drive_setup.md"
        )

    try:
        if has_service_account:
            return _check_drive_service_account()
        return _check_drive_oauth()
    except ImportError:
        return FAILED, "google-api-python-client / google-auth not installed. Run: pip install -r requirements.txt"
    except Exception as exc:
        return FAILED, f"could not list folder {GDRIVE_FOLDER_ID}: {exc}"


def check_snowflake() -> tuple:
    if not SNOWFLAKE_CONFIG.get("account") or not SNOWFLAKE_CONFIG.get("user"):
        return SKIPPED, "SNOWFLAKE_ACCOUNT/SNOWFLAKE_USER not set in .env; loader will run in dry-run mode"
    try:
        import snowflake.connector

        conn = snowflake.connector.connect(**get_snowflake_connect_kwargs(), login_timeout=15)
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_VERSION(), CURRENT_ACCOUNT(), CURRENT_USER()")
        version, account, user = cur.fetchone()
        cur.close()
        conn.close()
        return OK, f"connected as {user} to account {account} (Snowflake {version})"
    except ImportError:
        return FAILED, "snowflake-connector-python not installed. Run: pip install -r requirements.txt"
    except Exception as exc:
        return FAILED, f"could not connect: {exc}"


def check_slack() -> tuple:
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        return SKIPPED, "SLACK_BOT_TOKEN/SLACK_CHANNEL_ID not set in .env; notifications will print instead of sending"
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError

        client = WebClient(token=SLACK_BOT_TOKEN)
        auth = client.auth_test()
        channel = client.conversations_info(channel=SLACK_CHANNEL_ID)
        if not channel["channel"].get("is_member", True):
            return FAILED, f"bot is not a member of channel {SLACK_CHANNEL_ID}; invite it first"
        return OK, f"authenticated as {auth['user']}, channel {SLACK_CHANNEL_ID} reachable"
    except ImportError:
        return FAILED, "slack_sdk not installed. Run: pip install -r requirements.txt"
    except SlackApiError as exc:
        return FAILED, f"Slack API error: {exc.response['error']}"
    except Exception as exc:
        return FAILED, f"could not reach Slack: {exc}"


def check_smtp() -> tuple:
    if not SMTP_HOST or not SMTP_USER:
        return SKIPPED, "SMTP_HOST/SMTP_USER not set in .env; notifications will print instead of sending"
    try:
        import smtplib

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
        return OK, f"logged in to {SMTP_HOST}:{SMTP_PORT} as {SMTP_USER}"
    except socket.timeout:
        return FAILED, f"connection to {SMTP_HOST}:{SMTP_PORT} timed out"
    except Exception as exc:
        return FAILED, f"could not connect/login: {exc}"


CHECKS = [
    ("environment file (.env)", check_env_file),
    ("Google Drive", check_google_drive),
    ("Snowflake", check_snowflake),
    ("Slack", check_slack),
    ("SMTP / email", check_smtp),
]

ICON = {OK: "[OK]", SKIPPED: "[SKIPPED]", FAILED: "[FAILED]"}


def main(strict: bool):
    print("Checking CareSync connections before running any pipeline step...\n")
    results = []
    for name, check_fn in CHECKS:
        status, detail = check_fn()
        results.append((name, status, detail))
        print(f"{ICON[status]:<11} {name:<26} {detail}")

    print()
    failed = [r for r in results if r[1] == FAILED]
    skipped = [r for r in results if r[1] == SKIPPED]

    if failed:
        print(f"{len(failed)} connection(s) FAILED. Fix these before creating databases, "
              f"populating data, or running any live pipeline step.")
    if skipped:
        print(f"{len(skipped)} connection(s) SKIPPED (not configured). The pipeline will "
              f"fall back to local-simulation/dry-run mode for these instead of failing outright.")
    if not failed and not skipped:
        print("All connections OK. Safe to proceed with database creation, data population, "
              "and any pipeline step.")

    if strict and failed:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                         help="exit with a non-zero status if any check fails (useful in CI)")
    args = parser.parse_args()
    main(args.strict)
