-- CARESYNC_WH.RAW: one table per Synthea source file, columns loaded as-is
-- (text/variant tolerant) plus pipeline metadata. No transformation here.
-- Run once per environment: snowsql -f sql/ddl_raw.sql
--
-- Single database (CARESYNC_WH), separate schemas per layer (RAW / STAGING /
-- PROD / AUDIT). Access control between layers is enforced with Snowflake
-- roles and schema-level grants, not database boundaries, and dbt's
-- Snowflake convention is one target database with multiple schemas.

CREATE DATABASE IF NOT EXISTS CARESYNC_WH;
CREATE SCHEMA IF NOT EXISTS CARESYNC_WH.RAW;

-- Repeat this pattern for: organizations, providers, payers, patients,
-- encounters, conditions. Column lists below are the Synthea defaults,
-- adjust to match the exact export headers from the third-party agent.

CREATE TABLE IF NOT EXISTS CARESYNC_WH.RAW.PATIENTS (
    "Id" STRING,
    "BIRTHDATE" DATE,
    "DEATHDATE" DATE,
    "SSN" STRING,
    "FIRST" STRING,
    "LAST" STRING,
    "GENDER" STRING,
    "RACE" STRING,
    "ETHNICITY" STRING,
    "ADDRESS" STRING,
    "CITY" STRING,
    "STATE" STRING,
    "ZIP" STRING,
    _run_id STRING,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- TODO: ORGANIZATIONS, PROVIDERS, PAYERS, ENCOUNTERS, CONDITIONS tables,
-- one CREATE TABLE per Synthea CSV schema, same _run_id/_loaded_at pattern.
