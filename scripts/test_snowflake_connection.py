"""
Verifies Python can reach the Snowflake trial account configured in .env.

Usage:
    python -m scripts.test_snowflake_connection

Requires SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD (and
optionally SNOWFLAKE_ROLE / SNOWFLAKE_WAREHOUSE) set in .env. Runs
SELECT CURRENT_VERSION() as the simplest possible round trip. If this
succeeds, the warehouse is reachable and credentials are valid.
"""
import sys

from config.settings import SNOWFLAKE_CONFIG, get_snowflake_connect_kwargs


def main():
    if not SNOWFLAKE_CONFIG.get("account") or not SNOWFLAKE_CONFIG.get("user"):
        print("[test_snowflake_connection] SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER not set in .env. "
              "fill these in from your trial account (Snowsight -> Admin -> Accounts) before running this.")
        sys.exit(1)

    import snowflake.connector

    try:
        conn = snowflake.connector.connect(**get_snowflake_connect_kwargs())
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_VERSION(), CURRENT_ACCOUNT(), CURRENT_USER(), CURRENT_REGION()")
        version, account, user, region = cur.fetchone()
        print(f"[test_snowflake_connection] connected OK")
        print(f"  Snowflake version: {version}")
        print(f"  account:  {account}")
        print(f"  user:     {user}")
        print(f"  region:   {region}")
        cur.close()
        conn.close()
    except Exception as exc:
        print(f"[test_snowflake_connection] FAILED to connect: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
