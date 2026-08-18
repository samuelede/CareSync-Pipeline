-- CARESYNC_WH.STAGING: dbt staging models materialize here (views or tables,
-- set in dbt_caresync/dbt_project.yml). This is the PHI minimization
-- boundary. Staging models select every RAW column EXCEPT SSN, FIRST,
-- LAST, and any document/license numbers. Nothing downstream of staging
-- can re-expose PHI because it was never carried past this point.
--
-- No manual DDL needed here beyond the schema itself; dbt owns the tables.
CREATE SCHEMA IF NOT EXISTS CARESYNC_WH.STAGING;
