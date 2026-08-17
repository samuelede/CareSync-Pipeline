"""
Single source of truth for connection strings and pipeline constants.
Every script (validation, loaders, notifications, dbt invocation) imports from here
instead of reading os.environ directly, so there is exactly one place to change a
connection detail. This mirrors the convention used in the Mandera pipeline.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Google Drive ---
# Two supported auth methods, either can be left unset. Service account is
# preferred for automation, but some Google Cloud projects have service
# account key creation blocked by an organization policy
# (iam.disableServiceAccountKeyCreation). OAuth (your own Google account,
# via a one-time browser consent) works around that with no key file at
# all. See docs/google_drive_setup.md for the full setup and this
# troubleshooting case.
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_SERVICE_ACCOUNT_JSON = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON", "./config/gdrive_service_account.json")
GDRIVE_OAUTH_CLIENT_SECRET_JSON = os.getenv("GDRIVE_OAUTH_CLIENT_SECRET_JSON", "./config/gdrive_oauth_client_secret.json")
GDRIVE_OAUTH_TOKEN_JSON = os.getenv("GDRIVE_OAUTH_TOKEN_JSON", "./config/gdrive_oauth_token.json")

# --- Snowflake ---
# One database, one schema per pipeline layer (RAW / STAGING / PROD /
# AUDIT). Access control between layers is enforced with Snowflake roles
# and schema grants, not separate databases; dbt's Snowflake convention is
# one target database with multiple schemas.
SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "user": os.getenv("SNOWFLAKE_USER"),
    "password": os.getenv("SNOWFLAKE_PASSWORD"),
    "role": os.getenv("SNOWFLAKE_ROLE", "CARESYNC_LOADER"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "CARESYNC_WH"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "CARESYNC_WH"),
}
DATABASE = SNOWFLAKE_CONFIG["database"]
SCHEMA_RAW = "RAW"
SCHEMA_STAGING = "STAGING"
SCHEMA_PROD = "PROD"
SCHEMA_AUDIT = "AUDIT"

# --- Slack / Email ---
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "ops-team@nexorahealth.example")

# --- SLA ---
FILE_ARRIVAL_SLA_MINUTES = int(os.getenv("FILE_ARRIVAL_SLA_MINUTES", 60))
SCHEDULED_DELIVERY_TIME_UTC = os.getenv("SCHEDULED_DELIVERY_TIME_UTC", "06:00")

# --- Dataset manifest: dependency order matters for cascade-skip logic ---
# organizations/providers/payers are independent; patients is independent;
# encounters depends on patients + organizations + providers + payers;
# conditions depends on patients + encounters.
DATASET_MANIFEST = {
    "organizations": {"depends_on": []},
    "providers":     {"depends_on": ["organizations"]},
    "payers":        {"depends_on": []},
    "patients":      {"depends_on": []},
    "encounters":    {"depends_on": ["patients", "organizations", "providers", "payers"]},
    "conditions":    {"depends_on": ["patients", "encounters"]},
}
