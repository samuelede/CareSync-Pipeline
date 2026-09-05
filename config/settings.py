"""
Single source of truth for connection strings and pipeline constants.
Every script (validation, loaders, notifications, dbt invocation) imports from here
instead of reading os.environ directly, so there is exactly one place to change a
connection detail. This mirrors the convention used in the Mandera pipeline.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Validation engine ---
# "pandas" (default, Phase 1) or "great_expectations" (Phase 2). Both
# read the exact same validation.pandas.schemas.SCHEMAS definitions, so
# switching this never changes which rules are enforced, only how they're
# checked. See docs/architecture.md for the two-stage comparison.
VALIDATION_ENGINE = os.getenv("VALIDATION_ENGINE", "pandas")

# --- Google Drive ---
# Two supported auth methods, either can be left unset. Service account is
# preferred for automation, but some Google Cloud projects have service
# account key creation blocked by an organization policy
# (iam.disableServiceAccountKeyCreation). OAuth (your own Google account,
# via a one-time browser consent) works around that with no key file at
# all. See docs/google_drive_setup.md for the full setup and this
# troubleshooting case.
#
# GDRIVE_FORCE_LOCAL=true overrides both and forces local-simulation mode
# even if service account or OAuth credential files exist on disk. Useful
# while Drive auth is still being debugged, drop CSVs into
# data/landing/<run_id>/ by hand (or via scripts.simulate_weekly_drop) and
# run the pipeline without Drive at all, then flip this back to false once
# Drive access is sorted.
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
GDRIVE_SERVICE_ACCOUNT_JSON = os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON", "./config/gdrive_service_account.json")
GDRIVE_OAUTH_CLIENT_SECRET_JSON = os.getenv("GDRIVE_OAUTH_CLIENT_SECRET_JSON", "./config/gdrive_oauth_client_secret.json")
GDRIVE_OAUTH_TOKEN_JSON = os.getenv("GDRIVE_OAUTH_TOKEN_JSON", "./config/gdrive_oauth_token.json")
GDRIVE_FORCE_LOCAL = os.getenv("GDRIVE_FORCE_LOCAL", "false").lower() in ("true", "1", "yes")

# --- Snowflake ---
# Three databases, one per pipeline layer, per the platform's data
# architecture: NEXORA_RAW_WH (faithful, string-typed copies of validated
# files), NEXORA_STAGING_WH (typed and standardized), NEXORA_PROD_WH (the
# reporting marts). Each has one schema of the same name holding its
# tables; the run audit trail lives in NEXORA_RAW_WH.AUDIT.
#
# SNOWFLAKE_AUTH_METHOD selects how the pipeline authenticates:
#   password       (default) plain password login, works unless your
#                  account enforces MFA with a method the CLI/connector
#                  can't prompt for directly (e.g. a passkey).
#   externalbrowser  delegates login, including MFA, to a browser window.
#                  Requires your Snowflake account to have SAML/SSO
#                  federation configured (an identity provider like Okta);
#                  fails with a SAML-related error on plain trial accounts
#                  that don't have that set up.
#   keypair        RSA key-pair authentication. Bypasses password and MFA
#                  entirely, works on any account including plain trial
#                  accounts, and is the standard approach for programmatic
#                  or CI access anyway. See docs/snowflake_setup.md for
#                  generating a key pair and registering the public key.
SNOWFLAKE_AUTH_METHOD = os.getenv("SNOWFLAKE_AUTH_METHOD", "password")
SNOWFLAKE_PRIVATE_KEY_PATH = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH", "./config/snowflake_rsa_key.p8")
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")

DATABASE_RAW = os.getenv("SNOWFLAKE_DATABASE_RAW", "NEXORA_RAW_WH")
DATABASE_STAGING = os.getenv("SNOWFLAKE_DATABASE_STAGING", "NEXORA_STAGING_WH")
DATABASE_PROD = os.getenv("SNOWFLAKE_DATABASE_PROD", "NEXORA_PROD_WH")
SCHEMA_RAW = "RAW"
SCHEMA_STAGING = "STAGING"
SCHEMA_PROD = "PROD"
SCHEMA_AUDIT = "AUDIT"

SNOWFLAKE_CONFIG = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "user": os.getenv("SNOWFLAKE_USER"),
    "role": os.getenv("SNOWFLAKE_ROLE", "NEXORA_LOADER"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "NEXORA_WH"),
    # Initial connection database only, most queries fully-qualify with
    # DATABASE_RAW / DATABASE_STAGING / DATABASE_PROD regardless. RAW is
    # the default since sensing and loading (the first pipeline stages)
    # operate there.
    "database": DATABASE_RAW,
    "schema": "RAW",
}
if SNOWFLAKE_AUTH_METHOD == "password":
    SNOWFLAKE_CONFIG["password"] = os.getenv("SNOWFLAKE_PASSWORD")
elif SNOWFLAKE_AUTH_METHOD == "externalbrowser":
    SNOWFLAKE_CONFIG["authenticator"] = "externalbrowser"
elif SNOWFLAKE_AUTH_METHOD == "keypair":
    pass  # private_key bytes are loaded lazily, see get_snowflake_connect_kwargs() below


def get_snowflake_connect_kwargs() -> dict:
    """Returns kwargs ready for snowflake.connector.connect(**kwargs).

    Identical to SNOWFLAKE_CONFIG for password/externalbrowser auth. For
    keypair auth, loads and serializes the private key file at call time
    (not at import time) so a missing/misconfigured key file only breaks
    the actual connection attempt, not every import of this module.
    """
    if SNOWFLAKE_AUTH_METHOD != "keypair":
        return dict(SNOWFLAKE_CONFIG)

    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    with open(SNOWFLAKE_PRIVATE_KEY_PATH, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=SNOWFLAKE_PRIVATE_KEY_PASSPHRASE.encode() if SNOWFLAKE_PRIVATE_KEY_PASSPHRASE else None,
            backend=default_backend(),
        )
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return {**SNOWFLAKE_CONFIG, "private_key": private_key_bytes}

# --- Slack / Email ---
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")

# EMAIL_PROVIDER: "resend" (default, simplest, no app passwords) or "smtp"
# (any standard SMTP server: Gmail app password, SES, SendGrid's SMTP
# interface). Both send the same event matrix via the same
# send_email_alert() call, see notifications/email_notify.py.
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "CareSync <onboarding@resend.dev>")
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
NOTIFY_EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "ops-team@nexorahealth.example")

# --- SLA ---
# --- SFTP (Phase 2 production landing zone, replaces Google Drive) ---
SFTP_HOST = os.getenv("SFTP_HOST")
SFTP_PORT = int(os.getenv("SFTP_PORT", 22))
SFTP_USER = os.getenv("SFTP_USER")
SFTP_PASSWORD = os.getenv("SFTP_PASSWORD")
SFTP_KEY_PATH = os.getenv("SFTP_KEY_PATH")

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
