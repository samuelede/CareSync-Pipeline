# Snowflake Setup (first-time configuration)

This walks through everything needed to get a working Snowflake account,
the SnowSQL CLI, and the CareSync warehouse/database/schemas created.
Skip this if you're only running the pipeline in dry-run mode (no
`SNOWFLAKE_*` values set in `.env`), the loader and post-validation gate
fall back automatically and none of this is required.

## 1. Create a Snowflake trial account

1. Go to [signup.snowflake.com](https://signup.snowflake.com).
2. Fill in your details. For **Snowflake Edition**, pick **Standard**
   (sufficient for this project). Pick any cloud provider and region,
   it doesn't affect anything in this pipeline.
3. Check your email for the activation link and set a password.
4. Once activated, log in to Snowsight (Snowflake's web UI).

## 2. Find your account identifier

1. In Snowsight, go to **Admin > Accounts**.
2. Your account identifier is shown there, it looks like
   `xy12345.us-east-1` or `xy12345.us-east-1.aws`, depending on region.
   You'll use this to connect from both SnowSQL and Python.

## 3. Install SnowSQL (the CLI)

1. Go to the
   [Snowflake CLI clients page](https://docs.snowflake.com/en/user-guide/snowsql-install-config).
2. Download the installer for your OS (Windows `.msi`, macOS `.pkg`, or
   Linux `.bash`).
3. Run the installer.
4. Confirm it installed correctly:
   ```bash
   snowsql -v
   ```

## 4. Configure your first connection

```bash
snowsql -a <account_identifier> -u <username>
```

You'll be prompted for your password on first connect. If it connects
successfully, you'll land on a `>` prompt inside SnowSQL, type `!exit` to
leave.

**If this fails with an MFA error** like "MFA authentication is required,
but none of your current MFA methods are supported for programmatic
authentication", your enrolled MFA method (often a passkey/security key)
isn't one SnowSQL can prompt for directly. Skip to "MFA workaround:
key-pair authentication" below, that's the reliable fix on a plain trial
account. (`--authenticator externalbrowser` is the other commonly
suggested workaround, but it only works if your account has SAML/SSO
federation configured with an identity provider like Okta, it fails with
a SAML-related error on a plain trial account that doesn't have that set
up, which is the normal case here.)

Optionally, save the connection so you don't have to retype the account
and user every time. Edit (or create) `~/.snowsql/config` and add:

```
[connections.caresync]
accountname = <account_identifier>
username = <username>
```

Then connect any time with:

```bash
snowsql -c caresync
```

## MFA workaround: key-pair authentication

RSA key-pair authentication bypasses password and MFA entirely, on any
account type. It's also the standard approach for programmatic or CI
access generally, so this isn't really a workaround, it's the setup
you'd want eventually anyway.

**Generate a key pair** (run once, locally):

```bash
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out config/snowflake_rsa_key.p8 -nocrypt
openssl rsa -in config/snowflake_rsa_key.p8 -pubout -out config/snowflake_rsa_key_public.pem
```

This produces two files: `snowflake_rsa_key.p8` (private, never share or
commit it, already covered in `.gitignore`) and
`snowflake_rsa_key_public.pem` (public, safe to share, this is what
Snowflake stores).

**Register the public key on your Snowflake user.** This one step needs
to happen through a session that can already authenticate, use Snowsight
(the web UI) rather than the CLI, since browser-based login with your
existing MFA method works fine there, it's specifically CLI/programmatic
login that's blocked. Log in to Snowsight normally, open a worksheet, and
run:

```bash
cat config/snowflake_rsa_key_public.pem
```

Copy everything between `-----BEGIN PUBLIC KEY-----` and
`-----END PUBLIC KEY-----`, excluding those header/footer lines
themselves, then in the Snowsight worksheet:

```sql
ALTER USER <username> SET RSA_PUBLIC_KEY='<paste the key body here>';
```

**Verify it worked**, from the same worksheet:

```sql
DESC USER <username>;
```

Look for a `RSA_PUBLIC_KEY_FP` row with a non-empty fingerprint value.

**Connect with the key pair:**

```bash
snowsql -a <account_identifier> -u <username> --private-key-path config/snowflake_rsa_key.p8
```

If that connects without any password or MFA prompt, it worked. Set in
`.env`:

```bash
SNOWFLAKE_AUTH_METHOD=keypair
SNOWFLAKE_PRIVATE_KEY_PATH=./config/snowflake_rsa_key.p8
```

This makes `scripts.check_connections`, the loader, post-validation, and
(via the `dev_keypair` target in `dbt_caresync/profiles_example.yml`) dbt
itself all use the same key pair, no password or MFA prompt anywhere in
the pipeline.

## 5. Create the warehouse, database, and schemas

Run the project's DDL scripts once per environment. These create the
`CARESYNC_WH` warehouse and database, and the `RAW` / `STAGING` / `PROD` /
`AUDIT` schemas inside it (one database, four schemas, see the "Database
design note" in the main README for why).

```bash
snowsql -c caresync -f sql/ddl_raw.sql
snowsql -c caresync -f sql/ddl_staging.sql
snowsql -c caresync -f sql/ddl_prod.sql
snowsql -c caresync -f sql/run_audit_table.sql
```

If you haven't saved a named connection, replace `-c caresync` with
`-a <account_identifier> -u <username>` in each command.

Note that `sql/ddl_raw.sql` only creates the warehouse and database plus
the `PATIENTS` table as a worked example. Add the remaining
`ORGANIZATIONS`, `PROVIDERS`, `PAYERS`, `ENCOUNTERS`, and `CONDITIONS`
table definitions following the same `_run_id` / `_loaded_at` pattern
before loading real data.

## 6. Create a dedicated role and user (recommended, not required for a trial)

The DDL scripts run fine under your default trial account role. For
anything beyond local testing, create a scoped role so the pipeline's
credentials aren't your personal login:

```sql
CREATE ROLE IF NOT EXISTS CARESYNC_LOADER;
GRANT USAGE ON WAREHOUSE CARESYNC_WH TO ROLE CARESYNC_LOADER;
GRANT USAGE ON DATABASE CARESYNC_WH TO ROLE CARESYNC_LOADER;
GRANT ALL ON SCHEMA CARESYNC_WH.RAW TO ROLE CARESYNC_LOADER;
GRANT ALL ON SCHEMA CARESYNC_WH.STAGING TO ROLE CARESYNC_LOADER;
GRANT ALL ON SCHEMA CARESYNC_WH.PROD TO ROLE CARESYNC_LOADER;
GRANT ALL ON SCHEMA CARESYNC_WH.AUDIT TO ROLE CARESYNC_LOADER;
GRANT ROLE CARESYNC_LOADER TO USER <username>;
```

## 7. Fill in `.env`

```bash
SNOWFLAKE_ACCOUNT=<account_identifier>
SNOWFLAKE_USER=<username>
SNOWFLAKE_PASSWORD=<password>
SNOWFLAKE_ROLE=CARESYNC_LOADER
SNOWFLAKE_WAREHOUSE=CARESYNC_WH
SNOWFLAKE_DATABASE=CARESYNC_WH
SNOWFLAKE_AUTH_METHOD=password
```

`SNOWFLAKE_WAREHOUSE` and `SNOWFLAKE_DATABASE` intentionally share the
name `CARESYNC_WH`, they're different Snowflake object types (compute vs.
storage) and are allowed to share a name. Not a typo.

If step 4 needed the key-pair workaround because of an MFA error, set
these instead and leave `SNOWFLAKE_PASSWORD` blank:

```bash
SNOWFLAKE_AUTH_METHOD=keypair
SNOWFLAKE_PRIVATE_KEY_PATH=./config/snowflake_rsa_key.p8
```

## 8. Verify the connection

```bash
python -m scripts.check_connections
```

This should report `OK` for Snowflake, printing the Snowflake version,
account, user, and region. If it reports `FAILED`, the most common causes
are:

- Wrong account identifier format (missing or extra region/cloud suffix).
- Password typo, or the trial account's password was reset after
  inactivity.
- The role in `.env` doesn't exist yet or wasn't granted to the user
  (step 6).
- The warehouse or database wasn't created yet (step 5).

If Snowflake stays unconfigured, that's fine too, `loaders/snowflake_loader.py`
and `validation/pandas/post_validate.py` fall back to a dry-run mode that
proves the pipeline's control flow without ever touching a real warehouse.
