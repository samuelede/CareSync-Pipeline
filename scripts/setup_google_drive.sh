#!/usr/bin/env bash
# Automates the gcloud-scriptable parts of Google Drive service account
# setup: creating the project, enabling the Drive API, creating the
# service account, and generating the key. Two things gcloud has no
# command for and must stay manual (see docs/google_drive_setup.md):
#   - sharing the Drive folder with the service account's email
#   - OAuth "Desktop app" client creation (Path B), Console-only
#
# Usage:
#   ./scripts/setup_google_drive.sh <project-id> [service-account-name]
#
# Requires the Google Cloud CLI installed and authenticated:
#   https://cloud.google.com/sdk/docs/install
#   gcloud auth login
set -euo pipefail

PROJECT_ID="${1:?Usage: setup_google_drive.sh <project-id> [service-account-name]}"
SA_NAME="${2:-caresync-drive-reader}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_PATH="config/gdrive_service_account.json"

echo "[setup_google_drive] checking gcloud is installed and authenticated"
if ! command -v gcloud &> /dev/null; then
    echo "gcloud not found. Install it first: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "No active gcloud login found. Run: gcloud auth login"
    exit 1
fi

echo "[setup_google_drive] creating project ${PROJECT_ID} (skips if it already exists)"
if ! gcloud projects describe "${PROJECT_ID}" &> /dev/null; then
    gcloud projects create "${PROJECT_ID}" --name="${PROJECT_ID}"
else
    echo "  project already exists, continuing"
fi

echo "[setup_google_drive] setting active project"
gcloud config set project "${PROJECT_ID}"

echo "[setup_google_drive] enabling the Drive API"
gcloud services enable drive.googleapis.com

echo "[setup_google_drive] creating service account ${SA_EMAIL} (skips if it already exists)"
if ! gcloud iam service-accounts describe "${SA_EMAIL}" &> /dev/null; then
    gcloud iam service-accounts create "${SA_NAME}" \
        --display-name="CareSync Drive Reader"
else
    echo "  service account already exists, continuing"
fi

echo "[setup_google_drive] generating a JSON key"
mkdir -p config
set +e
gcloud iam service-accounts keys create "${KEY_PATH}" \
    --iam-account="${SA_EMAIL}" 2> /tmp/gdrive_key_error.log
KEY_EXIT=$?
set -e

if [ $KEY_EXIT -ne 0 ]; then
    if grep -qi "disableServiceAccountKeyCreation\|key creation is disabled" /tmp/gdrive_key_error.log; then
        echo ""
        echo "[setup_google_drive] key creation blocked by an organization policy"
        echo "(iam.disableServiceAccountKeyCreation). This is Google's 'Secure by"
        echo "Default' policy, common on newly created projects. Two options:"
        echo ""
        echo "  Option 1: override the policy for this project, if you have the"
        echo "  Organization Policy Administrator role, then re-run this script:"
        echo ""
        echo "    cat > /tmp/gdrive_policy.yaml << 'POLICY'"
        echo "    name: projects/${PROJECT_ID}/policies/iam.disableServiceAccountKeyCreation"
        echo "    spec:"
        echo "      rules:"
        echo "      - enforce: false"
        echo "    POLICY"
        echo "    gcloud org-policies set-policy /tmp/gdrive_policy.yaml"
        echo ""
        echo "  Option 2 (recommended): skip service accounts entirely and use"
        echo "  OAuth instead. See docs/google_drive_setup.md, Path B. This"
        echo "  script has already created the project and enabled the Drive"
        echo "  API for you, both are reused by Path B, only the credential"
        echo "  type differs from here."
        echo ""
        exit 1
    else
        cat /tmp/gdrive_key_error.log
        exit $KEY_EXIT
    fi
fi

echo ""
echo "[setup_google_drive] done. Key saved to ${KEY_PATH}"
echo ""
echo "Remaining manual steps (no CLI equivalent for these):"
echo "  1. Share your Drive delivery folder with this email as Viewer:"
echo "       ${SA_EMAIL}"
echo "  2. Copy the folder ID from its Drive URL:"
echo "       https://drive.google.com/drive/folders/<FOLDER_ID>"
echo "  3. Add to .env:"
echo "       GDRIVE_FOLDER_ID=<folder id from step 2>"
echo "       GDRIVE_SERVICE_ACCOUNT_JSON=./${KEY_PATH}"
echo "  4. Verify: python -m scripts.check_connections"
