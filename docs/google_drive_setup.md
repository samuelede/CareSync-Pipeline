# Google Drive API Setup (first-time configuration)

This walks through everything needed to get `GDRIVE_FOLDER_ID` and working
credentials so `sensing/drive_sensor.py` can reach a real Google Drive
folder in live mode. Skip this if you're only running the pipeline in
local-simulation mode (no `.env` values set for Drive), it falls back
automatically and none of this is required.

There are two ways to authenticate. Pick one.

- **Service account** (Path A): best for automation (GitHub Actions,
  Airflow), no browser interaction needed at run time. Requires
  downloading a JSON key file, which some Google Cloud projects block by
  default (see Troubleshooting below).
- **OAuth, your own Google account** (Path B): no key file at all, no
  organization policy to fight. Requires a one-time browser consent the
  first time you run the pipeline locally. Good default for local
  development and for projects where key creation is blocked.

Both paths share steps 1 and 2.

## 1. Create a Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Click the project dropdown at the top, then **New Project**.
3. Name it something like `caresync-pipeline`, and click **Create**.
4. Make sure the new project is selected in the project dropdown before
   continuing.

## 2. Enable the Google Drive API

1. In the left sidebar, go to **APIs & Services > Library**.
2. Search for "Google Drive API".
3. Click it, then click **Enable**.

---

## Path A: Service account

### A3. Create a service account

A service account is a non-human identity your Python code authenticates
as. It needs its own credentials, separate from your personal Google
login.

1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials > Service account**.
3. Give it a name, e.g. `caresync-drive-reader`. The service account ID
   and email are generated automatically.
4. Click **Create and Continue**.
5. On the "Grant this service account access to project" step, you can
   skip it (no project-level IAM role is needed, access is granted at the
   folder level in step A5 below). Click **Continue**, then **Done**.

### A4. Generate a JSON key

1. On the **Credentials** page, click the service account you just
   created.
2. Go to the **Keys** tab.
3. Click **Add Key > Create new key**.
4. Choose **JSON**, click **Create**. A `.json` file downloads
   automatically, this is your only copy, Google does not let you
   re-download it.
5. Move the downloaded file into the repo at:
   ```
   config/gdrive_service_account.json
   ```
   This path matches `GDRIVE_SERVICE_ACCOUNT_JSON` in `.env.example`. It's
   already excluded in `.gitignore`, it will never be committed.

If step A4.4 fails with **"Service account key creation is disabled"**,
see Troubleshooting below, then either fix the organization policy or
switch to Path B.

### A5. Share the delivery folder with the service account

The service account has its own email address, something like
`caresync-drive-reader@caresync-pipeline.iam.gserviceaccount.com`. Find it
on the service account's details page, or inside the JSON key file under
the `client_email` field.

1. In Google Drive, create (or locate) the folder that will act as the
   weekly delivery drop zone.
2. Right-click the folder, choose **Share**.
3. Paste in the service account's email address.
4. Set its permission to **Viewer** (the pipeline only reads files, it
   never writes to Drive).
5. Click **Send** (no real email is sent to a service account, but the
   button confirms the share).

### A6. Get the folder ID and fill in `.env`

1. Open the folder in Google Drive in your browser.
2. Look at the URL: `https://drive.google.com/drive/folders/<FOLDER_ID>`.
3. Copy the `<FOLDER_ID>` portion.

```bash
GDRIVE_FOLDER_ID=<the folder id>
GDRIVE_SERVICE_ACCOUNT_JSON=./config/gdrive_service_account.json
```

Skip ahead to "Verify the connection" below.

---

## Troubleshooting: "Service account key creation is disabled"

This means an organization policy called
`iam.disableServiceAccountKeyCreation` is enforced on the project. Google
started enforcing this automatically on many newly created projects
(including personal, non-Workspace accounts) as part of "Secure by
Default", it isn't specific to anything you did wrong.

You have two options:

**Option 1: disable the policy (if you have permission).** Go to
**IAM & Admin > Organization Policies**, search for
`iam.disableServiceAccountKeyCreation`, open it, and add a rule to
override the enforced constraint for this project. This requires the
"Organization Policy Administrator" role (`roles/orgpolicy.policyAdmin`).
On a personal account with no formal organization, you may already have
this role implicitly, on an account tied to a Google Workspace
organization, you may need to ask an admin.

**Option 2 (recommended): switch to Path B, OAuth.** No key file, no
organization policy involved at all. This sidesteps the problem entirely
and is the simpler path for local development anyway. Continue below.

---

## Path B: OAuth (your own Google account, no service account key)

### B3. Create an OAuth client ID

1. Go to **APIs & Services > Credentials**.
2. If prompted, configure the **OAuth consent screen** first: choose
   **External** (unless you have a Workspace organization), fill in an
   app name and your email for the required fields, and add your own
   Google account under **Test users** (the app stays in "Testing" mode,
   which is fine, it never needs Google's review for personal use).
3. Back on **Credentials**, click **Create Credentials > OAuth client ID**.
4. Application type: **Desktop app**.
5. Give it a name, e.g. `caresync-drive-oauth`, click **Create**.
6. Click **Download JSON** on the client ID you just created.
7. Move the downloaded file into the repo at:
   ```
   config/gdrive_oauth_client_secret.json
   ```
   This path matches `GDRIVE_OAUTH_CLIENT_SECRET_JSON` in `.env.example`.
   Already excluded in `.gitignore`.

Unlike a service account key, this file alone doesn't grant access to
anything, it just identifies the app requesting access. The actual
consent and resulting token come from you, in step B5.

### B4. Get the folder ID and fill in `.env`

Since Drive is accessed as your own account under this path, you don't
need to share the folder with anyone, you already own or have access to
it.

1. Open the folder in Google Drive in your browser.
2. Look at the URL: `https://drive.google.com/drive/folders/<FOLDER_ID>`.
3. Copy the `<FOLDER_ID>` portion.

```bash
GDRIVE_FOLDER_ID=<the folder id>
GDRIVE_OAUTH_CLIENT_SECRET_JSON=./config/gdrive_oauth_client_secret.json
GDRIVE_OAUTH_TOKEN_JSON=./config/gdrive_oauth_token.json
```

Leave `GDRIVE_SERVICE_ACCOUNT_JSON`'s file absent (or delete
`config/gdrive_service_account.json` if it exists), `sensing/drive_sensor.py`
checks for a service account key first and only falls back to OAuth if
that file isn't present.

### B5. Complete the one-time browser consent

```bash
python -m sensing.drive_sensor --run-id oauth-setup-check
```

The first run opens a browser window asking you to sign in and approve
read-only Drive access. Once approved, a token is cached at
`config/gdrive_oauth_token.json` and reused (and silently refreshed)
automatically on every future run, no browser interaction needed again
unless the token is revoked or deleted.

Note this step needs a local browser, it won't work unattended in a
headless CI environment. GitHub Actions and Airflow runs should use Path A
(service account) once the organization policy is resolved, or fall back
to local-simulation mode for the CI parts of this project.

---

## Verify the connection

```bash
python -m scripts.check_connections
```

This should report `OK` for Google Drive, for either path. If it reports
`FAILED`, the most common causes are:

- **Path A**: the folder wasn't actually shared with the service
  account's email (step A5), double check the exact email address
  matches what's in the JSON key file. Or the Drive API isn't enabled on
  the project (step 2).
- **Path B**: the one-time browser consent (step B5) hasn't been
  completed yet, `check_connections.py` can't open a browser itself, only
  `drive_sensor.py`'s first run can.
- Either path: `GDRIVE_FOLDER_ID` doesn't match an actual folder, or the
  relevant JSON file path in `.env` doesn't point at where the file
  actually is.

If Drive stays unconfigured, that's fine too, `sensing/drive_sensor.py`
and `scripts/simulate_weekly_drop.py` let you build and test the entire
pipeline locally without ever touching a real Drive folder.
