# Data Dictionary

## Source files (Synthea, in scope)

| Dataset | Grain | Key fields | Notes |
|---|---|---|---|
| organizations | one row per clinic/org | Id, NAME, ADDRESS | independent (no upstream FK); becomes `dim_clinics` in PROD |
| providers | one row per provider | Id, ORGANIZATION, NAME | depends on organizations |
| payers | one row per payer | Id, NAME | independent |
| patients | one row per patient | Id, SSN, FIRST, LAST, BIRTHDATE | independent; SSN/FIRST/LAST are PHI, stripped at staging |
| encounters | one row per patient visit, treated as one appointment | Id, PATIENT, ORGANIZATION, PROVIDER, PAYER, START, STOP | depends on patients, organizations, providers, payers |
| conditions | one row per diagnosed condition | PATIENT, ENCOUNTER, CODE, DESCRIPTION | depends on patients, encounters |

## PHI minimization

Dropped at the `staging` layer (`dbt_caresync/models/staging/stg_patients.sql`)
and never selected into any downstream model: `SSN`, `FIRST`, `LAST`, and
any license/document number columns.

## PROD star schema

See [`docs/entity_relationship.md`](entity_relationship.md) for the full
diagram.

- `fct_appointments`: one row per encounter, in `NEXORA_PROD_WH.PROD`
- `dim_patients`, `dim_providers`, `dim_clinics`, `dim_payers`
- `conditions_detail`: one row per condition, FK to `fct_appointments`
