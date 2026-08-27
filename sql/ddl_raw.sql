-- NEXORA_RAW_WH: faithful, string-typed copies of validated files. One
-- table per Synthea source file, every column loaded as STRING, no
-- casting, no cleaning. Typing and standardization happen downstream in
-- dbt's staging models (NEXORA_STAGING_WH), not here, so RAW always reflects
-- exactly what the validated file contained.
--
-- Run once per environment: snowsql -f sql/ddl_raw.sql
--
-- Column names are double-quoted to preserve the exact mixed-case headers
-- Synthea exports use (e.g. "Id", not "ID"). dbt's staging models
-- reference these same quoted, case-sensitive names via source(), so the
-- casing here must match exactly. Verified against a real Synthea CSV
-- export (synthetichealth/synthea-sample-data), not just the schema
-- documented from memory, see validation/pandas/schemas.py for details
-- on what that verification changed.

CREATE WAREHOUSE IF NOT EXISTS NEXORA_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE;

CREATE DATABASE IF NOT EXISTS NEXORA_RAW_WH;
CREATE SCHEMA IF NOT EXISTS NEXORA_RAW_WH.RAW;

CREATE TABLE IF NOT EXISTS NEXORA_RAW_WH.RAW.ORGANIZATIONS (
    "Id"          STRING,
    "NAME"        STRING,
    "ADDRESS"     STRING,
    "CITY"        STRING,
    "STATE"       STRING,
    "ZIP"         STRING,
    "LAT"         STRING,
    "LON"         STRING,
    "PHONE"       STRING,
    "REVENUE"     STRING,
    "UTILIZATION" STRING,
    "NPI"         STRING,
    _run_id STRING,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS NEXORA_RAW_WH.RAW.PROVIDERS (
    "Id"           STRING,
    "ORGANIZATION" STRING,
    "NAME"         STRING,
    "GENDER"       STRING,
    "SPECIALITY"   STRING,
    "ADDRESS"      STRING,
    "CITY"         STRING,
    "STATE"        STRING,
    "ZIP"          STRING,
    "LAT"          STRING,
    "LON"          STRING,
    "ENCOUNTERS"   STRING,
    "PROCEDURES"   STRING,
    "NPI"          STRING,
    _run_id STRING,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS NEXORA_RAW_WH.RAW.PAYERS (
    "Id"                     STRING,
    "NAME"                   STRING,
    "OWNERSHIP"              STRING,
    "ADDRESS"                STRING,
    "CITY"                   STRING,
    "STATE_HEADQUARTERED"    STRING,
    "ZIP"                    STRING,
    "PHONE"                  STRING,
    "AMOUNT_COVERED"         STRING,
    "AMOUNT_UNCOVERED"       STRING,
    "REVENUE"                STRING,
    "COVERED_ENCOUNTERS"     STRING,
    "UNCOVERED_ENCOUNTERS"   STRING,
    "COVERED_MEDICATIONS"    STRING,
    "UNCOVERED_MEDICATIONS"  STRING,
    "COVERED_PROCEDURES"     STRING,
    "UNCOVERED_PROCEDURES"   STRING,
    "COVERED_IMMUNIZATIONS"  STRING,
    "UNCOVERED_IMMUNIZATIONS" STRING,
    "UNIQUE_CUSTOMERS"       STRING,
    "QOLS_AVG"               STRING,
    "MEMBER_MONTHS"          STRING,
    _run_id STRING,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS NEXORA_RAW_WH.RAW.PATIENTS (
    "Id"                    STRING,
    "BIRTHDATE"             STRING,
    "DEATHDATE"             STRING,
    "SSN"                   STRING,
    "DRIVERS"               STRING,
    "PASSPORT"              STRING,
    "PREFIX"                STRING,
    "FIRST"                 STRING,
    "MIDDLE"                STRING,
    "LAST"                  STRING,
    "SUFFIX"                STRING,
    "MAIDEN"                STRING,
    "MARITAL"               STRING,
    "RACE"                  STRING,
    "ETHNICITY"             STRING,
    "GENDER"                STRING,
    "BIRTHPLACE"            STRING,
    "ADDRESS"               STRING,
    "CITY"                  STRING,
    "STATE"                 STRING,
    "COUNTY"                STRING,
    "FIPS"                  STRING,
    "ZIP"                   STRING,
    "LAT"                   STRING,
    "LON"                   STRING,
    "HEALTHCARE_EXPENSES"   STRING,
    "HEALTHCARE_COVERAGE"   STRING,
    "INCOME"                STRING,
    _run_id STRING,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS NEXORA_RAW_WH.RAW.ENCOUNTERS (
    "Id"                   STRING,
    "START"                STRING,
    "STOP"                 STRING,
    "PATIENT"              STRING,
    "ORGANIZATION"         STRING,
    "PROVIDER"             STRING,
    "PAYER"                STRING,
    "ENCOUNTERCLASS"       STRING,
    "CODE"                 STRING,
    "DESCRIPTION"          STRING,
    "BASE_ENCOUNTER_COST"  STRING,
    "TOTAL_CLAIM_COST"     STRING,
    "PAYER_COVERAGE"       STRING,
    "REASONCODE"           STRING,
    "REASONDESCRIPTION"    STRING,
    _run_id STRING,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS NEXORA_RAW_WH.RAW.CONDITIONS (
    "START"       STRING,
    "STOP"        STRING,
    "PATIENT"     STRING,
    "ENCOUNTER"   STRING,
    "SYSTEM"      STRING,
    "CODE"        STRING,
    "DESCRIPTION" STRING,
    _run_id STRING,
    _loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);