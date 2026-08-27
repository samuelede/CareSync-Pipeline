# Data Dictionary

Verified against a real Synthea CSV export (`synthetichealth/synthea-sample-data`
on GitHub, csv bundle, 108 patients / 5571 encounters / 3517 conditions),
not just the schema recalled from memory. A trimmed copy (referentially
intact, 316KB) is committed at `data/real_synthea_sample/` for tests and
exploration; `scripts/explore_synthea_data.py` re-runs this verification
against any Synthea export, and found zero schema drift and zero
referential-integrity violations on both the trimmed copy and the full
5571-row download.

## Source files (Synthea, in scope)

| Dataset | Grain | Full column list | Notes |
|---|---|---|---|
| organizations | one row per clinic/org | Id, NAME, ADDRESS, CITY, STATE, ZIP, LAT, LON, PHONE, REVENUE, UTILIZATION, NPI | independent (no upstream FK); becomes `dim_clinics` in PROD |
| providers | one row per provider | Id, ORGANIZATION, NAME, GENDER, SPECIALITY, ADDRESS, CITY, STATE, ZIP, LAT, LON, ENCOUNTERS, PROCEDURES, NPI | depends on organizations |
| payers | one row per payer | Id, NAME, OWNERSHIP, ADDRESS, CITY, STATE_HEADQUARTERED, ZIP, PHONE, AMOUNT_COVERED, AMOUNT_UNCOVERED, REVENUE, COVERED_ENCOUNTERS, UNCOVERED_ENCOUNTERS, COVERED_MEDICATIONS, UNCOVERED_MEDICATIONS, COVERED_PROCEDURES, UNCOVERED_PROCEDURES, COVERED_IMMUNIZATIONS, UNCOVERED_IMMUNIZATIONS, UNIQUE_CUSTOMERS, QOLS_AVG, MEMBER_MONTHS | independent |
| patients | one row per patient | Id, BIRTHDATE, DEATHDATE, SSN, DRIVERS, PASSPORT, PREFIX, FIRST, MIDDLE, LAST, SUFFIX, MAIDEN, MARITAL, RACE, ETHNICITY, GENDER, BIRTHPLACE, ADDRESS, CITY, STATE, COUNTY, FIPS, ZIP, LAT, LON, HEALTHCARE_EXPENSES, HEALTHCARE_COVERAGE, INCOME | independent; SSN/FIRST/MIDDLE/LAST are PHI, stripped at staging |
| encounters | one row per patient visit, treated as one appointment | Id, START, STOP, PATIENT, ORGANIZATION, PROVIDER, PAYER, ENCOUNTERCLASS, CODE, DESCRIPTION, BASE_ENCOUNTER_COST, TOTAL_CLAIM_COST, PAYER_COVERAGE, REASONCODE, REASONDESCRIPTION | depends on patients, organizations, providers, payers |
| conditions | one row per diagnosed condition | START, STOP, PATIENT, ENCOUNTER, SYSTEM, CODE, DESCRIPTION | depends on patients, encounters |

`ENCOUNTERCLASS` allowed values (verified against real data, not just the
commonly-documented subset): `ambulatory`, `emergency`, `inpatient`,
`wellness`, `urgentcare`, `outpatient`, `home`, `virtual`, `hospice`, `snf`.

## PHI minimization

Dropped at the `staging` layer (`dbt_caresync/models/staging/stg_patients.sql`)
and never selected into any downstream model: `SSN`, `FIRST`, `MIDDLE`,
`LAST`, `DRIVERS`, `PASSPORT`, `PREFIX`, `SUFFIX`, `MAIDEN`. `INCOME` is
also excluded, not a HIPAA identifier, but unrelated to clinic/appointment
reporting and there's no reason to carry it past RAW.

## PROD star schema

See [`docs/entity_relationship.md`](entity_relationship.md) for the full
diagram.

- `fct_appointments`: one row per encounter, in `NEXORA_PROD_WH.PROD`
- `dim_patients`, `dim_providers`, `dim_clinics`, `dim_payers`
- `conditions_detail`: one row per condition, FK to `fct_appointments`
