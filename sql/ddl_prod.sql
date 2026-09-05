-- NEXORA_PROD_WH: the reporting marts. dbt mart models materialize here, the
-- single-fact star schema. dbt owns table creation; this file documents
-- the target shape. See docs/entity_relationship.md for the diagram.
--
--   fct_appointments   one row per encounter (the fact table)
--     - patient_key (FK -> dim_patients)
--     - provider_key (FK -> dim_providers)
--     - clinic_key (FK -> dim_clinics)
--     - payer_key (FK -> dim_payers)
--     - start_ts, stop_ts, encounter_class, base_encounter_cost,
--       total_claim_cost, payer_coverage
--   dim_patients   patient attributes, PHI stripped at staging
--   dim_providers  provider attributes
--   dim_clinics    clinic/organization attributes
--   dim_payers     payer attributes
--   conditions_detail   one row per condition, FK -> fct_appointments
--
-- Run once per environment: snowsql -f sql/ddl_prod.sql
CREATE DATABASE IF NOT EXISTS NEXORA_PROD_WH;
CREATE SCHEMA IF NOT EXISTS NEXORA_PROD_WH.PROD;
