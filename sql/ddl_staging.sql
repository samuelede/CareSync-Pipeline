-- NEXORA_STAGING_WH: typed and standardized. dbt staging models materialize
-- here (views or tables, set in dbt_caresync/dbt_project.yml), casting
-- RAW's string columns to real types and renaming to snake_case. This is
-- also the PHI minimization boundary: staging models select every RAW
-- column EXCEPT SSN, FIRST, LAST, and any document/license numbers.
-- Nothing downstream of staging can re-expose PHI because it was never
-- carried past this point.
--
-- No manual DDL needed here beyond the database and schema; dbt owns the
-- tables. Run once per environment: snowsql -f sql/ddl_staging.sql
CREATE DATABASE IF NOT EXISTS NEXORA_STAGING_WH;
CREATE SCHEMA IF NOT EXISTS NEXORA_STAGING_WH.STAGING;
