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

**If `snowsql -c caresync` says "No connection could be found"**, the
config file wasn't created, or wasn't saved where SnowSQL looks for it.
Fix directly from the terminal:

```bash
mkdir -p ~/.snowsql
cat > ~/.snowsql/config << 'EOF'
[connections.caresync]
accountname = <account_identifier>
username = <username>
private_key_path = config/snowflake_rsa_key.p8
EOF
```

Omit the `private_key_path` line if you're using password login instead
of key-pair auth. Verify it saved, then retry:

```bash
cat ~/.snowsql/config
snowsql -c caresync
```

If it still fails, `private_key_path` is relative to your terminal's
current directory when you run the command, not the repo root
permanently. Either always run `snowsql -c caresync` from the repo root,
or switch the config to an absolute path.

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

## 5. Create the warehouse and the three databases

Run the project's DDL scripts once per environment. `sql/ddl_raw.sql`
creates the shared `NEXORA_WH` warehouse plus the `NEXORA_RAW_WH` database,
schema, and all six RAW tables (every column typed as STRING; typing
happens later in dbt). `sql/ddl_staging.sql` and `sql/ddl_prod.sql`
create the `NEXORA_STAGING_WH` and `NEXORA_PROD_WH` databases (dbt owns the
tables inside them). `sql/run_audit_table.sql` creates the audit trail.

```bash
snowsql -c caresync -f sql/ddl_raw.sql
snowsql -c caresync -f sql/ddl_staging.sql
snowsql -c caresync -f sql/ddl_prod.sql
snowsql -c caresync -f sql/run_audit_table.sql
```

If you haven't saved a named connection, replace `-c caresync` with
`-a <account_identifier> -u <username>` in each command.

## 6. Create a dedicated role and user (recommended, not required for a trial)

The DDL scripts run fine under your default trial account role. For
anything beyond local testing, create a scoped role so the pipeline's
credentials aren't your personal login. This role needs `USAGE` on all
three databases since dbt's staging models read `NEXORA_RAW_WH` while
writing to `NEXORA_STAGING_WH`, and marts write to `NEXORA_PROD_WH`:

```sql
CREATE ROLE IF NOT EXISTS NEXORA_LOADER;
GRANT USAGE ON WAREHOUSE NEXORA_WH TO ROLE NEXORA_LOADER;

GRANT USAGE ON DATABASE NEXORA_RAW_WH TO ROLE NEXORA_LOADER;
GRANT ALL ON SCHEMA NEXORA_RAW_WH.RAW TO ROLE NEXORA_LOADER;
GRANT ALL ON SCHEMA NEXORA_RAW_WH.AUDIT TO ROLE NEXORA_LOADER;

GRANT USAGE ON DATABASE NEXORA_STAGING_WH TO ROLE NEXORA_LOADER;
GRANT ALL ON SCHEMA NEXORA_STAGING_WH.STAGING TO ROLE NEXORA_LOADER;

GRANT USAGE ON DATABASE NEXORA_PROD_WH TO ROLE NEXORA_LOADER;
GRANT ALL ON SCHEMA NEXORA_PROD_WH.PROD TO ROLE NEXORA_LOADER;

GRANT ROLE NEXORA_LOADER TO USER <username>;
```

## 7. Fill in `.env`

```bash
SNOWFLAKE_ACCOUNT=<account_identifier>
SNOWFLAKE_USER=<username>
SNOWFLAKE_PASSWORD=<password>
SNOWFLAKE_ROLE=NEXORA_LOADER
SNOWFLAKE_WAREHOUSE=NEXORA_WH
SNOWFLAKE_DATABASE_RAW=NEXORA_RAW_WH
SNOWFLAKE_DATABASE_STAGING=NEXORA_STAGING_WH
SNOWFLAKE_DATABASE_PROD=NEXORA_PROD_WH
SNOWFLAKE_AUTH_METHOD=password
```

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

Successful output looks like this:

```
[OK]        Snowflake                  connected as <username> to account <account> (Snowflake <version>)
```

If it reports `FAILED`, the most common causes are:

- Wrong account identifier format (missing or extra region/cloud suffix).
- Password typo, or the trial account's password was reset after
  inactivity.
- The role in `.env` doesn't exist yet or wasn't granted to the user
  (step 6).
- The warehouse or database wasn't created yet (step 5).

If Snowflake stays unconfigured, that's fine too, `loaders/snowflake_loader.py`
and `validation/pandas/post_validate.py` fall back to a dry-run mode that
proves the pipeline's control flow without ever touching a real warehouse.
