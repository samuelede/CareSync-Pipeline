# Google Drive API Setup (first-time configuration)

This walks through everything needed to get `GDRIVE_FOLDER_ID` and working
credentials so `sensing/drive_sensor.py` can reach a real Google Drive
folder in live mode. **None of this is required to run the pipeline.**
Skip it entirely, or come back to it later, by dropping CSVs into
`data/landing/<run_id>/` yourself, either downloaded by hand or generated
with `python -m scripts.simulate_weekly_drop --run-id <run_id>`. If
Drive credentials happen to exist on disk from a partial setup attempt,
set `GDRIVE_FORCE_LOCAL=true` in `.env` to force local mode regardless,
so debugging Drive access later doesn't require deleting anything first.

There are two ways to authenticate. Pick one.

- **Service account** (Path A): best for automation (GitHub Actions,
  Airflow), no browser interaction needed at run time. Requires
  downloading a JSON key file, which some Google Cloud projects block by
  default (see Troubleshooting below). Steps 1, 2, A3, and A4 can all be
  done from the command line, see Path A, step A0.
- **OAuth, your own Google account** (Path B): no key file at all, no
  organization policy to fight. Requires a one-time browser consent the
  first time you run the pipeline locally. Good default for local
  development and for projects where key creation is blocked. Steps 1 and
  2 can be done from the command line (reuse Path A's script, step A0, and
  stop before key creation); creating the OAuth client ID itself (step B3)
  has no CLI equivalent, Google only exposes it through the Console.

Both paths share steps 1 and 2 below, or the CLI script in Path A, step A0,
which does both automatically either way.

## 1. Create a Google Cloud project

**Command line:**
```bash
gcloud projects create caresync-pipeline --name=caresync-pipeline
gcloud config set project caresync-pipeline
```

**Or via the Console:**
1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Click the project dropdown at the top, then **New Project**.
3. Name it something like `caresync-pipeline`, and click **Create**.
4. Make sure the new project is selected in the project dropdown before
   continuing.

## 2. Enable the Google Drive API

**Command line:**
```bash
gcloud services enable drive.googleapis.com
```

**Or via the Console:**
1. In the left sidebar, go to **APIs & Services > Library**.
2. Search for "Google Drive API".
3. Click it, then click **Enable**.

---

## Path A: Service account

### A0. CLI-automated setup (recommended over clicking through the Console)

If you have the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)
installed, one script handles project creation, enabling the Drive API,
creating the service account, and generating the key:

```bash
gcloud auth login
./scripts/setup_google_drive.sh caresync-pipeline
```

The second argument is optional (service account name, defaults to
`caresync-drive-reader`). The script is idempotent, safe to re-run if a
project or service account already exists. If it hits the key-creation-
disabled organization policy, it prints the exact fix or points you at
Path B, see Troubleshooting below either way.

This automates everything through step A4. Skip to step A5 (sharing the
folder) once it finishes, that part and OAuth client creation (Path B)
are the only two steps with no `gcloud` equivalent, Google only exposes
them through the Console UI.

If you'd rather click through the Console instead (or don't have `gcloud`
installed), continue with steps A3-A4 below, they do the same thing
manually.

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

1. Go to [drive.google.com](https://drive.google.com) and double-click
   the folder you shared in step A5, so you're inside it, not just
   looking at it in a list.
2. Look at the browser's address bar. It'll look like:
   ```
   https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456
   ```
3. Everything after `/folders/` is the folder ID, copy just that part.

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

**Option 1: disable the policy (if you have permission), via the CLI.**
```bash
cat > /tmp/gdrive_policy.yaml << 'POLICY'
name: projects/<your-project-id>/policies/iam.disableServiceAccountKeyCreation
spec:
  rules:
  - enforce: false
POLICY
gcloud org-policies set-policy /tmp/gdrive_policy.yaml
```
Requires the "Organization Policy Administrator" role
(`roles/orgpolicy.policyAdmin`). On a personal account with no formal
organization, you may already have this role implicitly, on an account
tied to a Google Workspace organization, you may need to ask an admin.
`scripts/setup_google_drive.sh` prints this exact command, with your
project ID already filled in, if it hits this error. Or do the equivalent
by hand in the Console: **IAM & Admin > Organization Policies**, search
for `iam.disableServiceAccountKeyCreation`, open it, add an override rule.

**Option 2 (recommended): switch to Path B, OAuth.** No key file, no
organization policy involved at all. This sidesteps the problem entirely
and is the simpler path for local development anyway. Continue below.

---

## Troubleshooting: "Access blocked: can only be used within its organization" (Error 403: org_internal)

This happens if the OAuth consent screen's **User type** was set to
**Internal** instead of **External** in step B3. Internal restricts sign-in
to accounts on a specific Workspace organization's domain, which a
personal Gmail account is never part of, so you get blocked trying to
sign in as yourself.

**Fix:**

1. In [console.cloud.google.com](https://console.cloud.google.com), go to
   **APIs & Services > OAuth consent screen**.
2. If **User type** can still be edited, change it to **External**, then
   add your Google account under **Test users**.
3. If it's locked (Google doesn't always allow changing this after the
   fact), the simplest fix is a fresh project:
   ```bash
   gcloud projects create caresync-pipeline-2
   gcloud config set project caresync-pipeline-2
   gcloud services enable drive.googleapis.com
   ```
   Then repeat step B3 from the start on the new project, choosing
   **External** this time.
4. Recreate the OAuth client ID, download the new JSON, and overwrite
   `config/gdrive_oauth_client_secret.json`.
5. Delete the stale cached token so the next run re-triggers consent
   against the new client:
   ```bash
   rm config/gdrive_oauth_token.json
   ```
6. Re-run `python -m sensing.drive_sensor --run-id oauth-retest` and
   complete the browser consent again.

---

## Path B: OAuth (your own Google account, no service account key)

### B3. Create an OAuth client ID

1. Go to **APIs & Services > Credentials**.
2. If prompted, configure the **OAuth consent screen** first: for
   **User type**, choose **External**. If you have a personal Gmail
   account (not tied to a Google Workspace organization), this is almost
   always the right choice, even if **Internal** is offered as an option.
   Choosing **Internal** by mistake causes an
   `Error 403: org_internal` / "can only be used within its organization"
   screen when you try to sign in later, see Troubleshooting below if you
   hit that.
3. Fill in an app name and your email for the required fields, then add
   your own Google account under **Test users** (the app stays in
   "Testing" mode, which is fine, it never needs Google's review for
   personal use).
4. Back on **Credentials**, click **Create Credentials > OAuth client ID**.
5. Application type: **Desktop app**.
6. Give it a name, e.g. `caresync-drive-oauth`, click **Create**.
7. Click **Download JSON** on the client ID you just created.
8. Move the downloaded file into the repo at:
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
it. If you don't have a delivery folder yet, create one first.

1. Go to [drive.google.com](https://drive.google.com), signed in with the
   **same Google account** you used for the OAuth consent screen in B3
   (this matters, OAuth only grants access to the account that approved
   it).
2. No existing folder to use? Click **+ New > New folder**, name it
   something like `caresync-weekly-drop`, click **Create**.
3. Double-click the folder to open it, so you're inside it, not just
   looking at it in a list.
4. Look at the browser's address bar. It'll look like:
   ```
   https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz0123456
   ```
5. Everything after `/folders/` is the folder ID, copy just that part.

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
