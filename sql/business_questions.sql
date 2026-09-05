-- Answers to the reporting and data-quality business questions, run
-- against NEXORA_PROD_WH.PROD once fct_appointments + dimensions exist.
-- Fill in each query against the actual mart column names once dbt has run.

-- Q1: Weekly appointment volume by clinic
-- SELECT c.clinic_name, COUNT(*) AS appointments
-- FROM NEXORA_PROD_WH.PROD.fct_appointments f
-- JOIN NEXORA_PROD_WH.PROD.dim_clinics c USING (clinic_key)
-- GROUP BY 1 ORDER BY 2 DESC;

-- Q2: Provider workload, appointments per provider, current run
-- SELECT p.provider_name, COUNT(*) AS appointments
-- FROM NEXORA_PROD_WH.PROD.fct_appointments f
-- JOIN NEXORA_PROD_WH.PROD.dim_providers p USING (provider_key)
-- WHERE f._run_id = :run_id GROUP BY 1 ORDER BY 2 DESC;

-- Q3: Payer coverage mix
-- SELECT pay.payer_name, COUNT(*) AS appointments, SUM(f.payer_coverage) AS total_covered
-- FROM NEXORA_PROD_WH.PROD.fct_appointments f
-- JOIN NEXORA_PROD_WH.PROD.dim_payers pay USING (payer_key)
-- GROUP BY 1 ORDER BY 2 DESC;

-- Q4: Data-quality question, runs with any REJECTED or SKIPPED dataset
-- SELECT run_id, dataset, status FROM NEXORA_RAW_WH.AUDIT.RUN_AUDIT
-- WHERE status IN ('REJECTED', 'SKIPPED') ORDER BY recorded_at DESC;

-- Q5: SLA performance, percent of files on time over the last N runs
-- SELECT dataset, AVG(IFF(status = 'ON_TIME', 1, 0)) AS pct_on_time
-- FROM NEXORA_RAW_WH.AUDIT.RUN_AUDIT WHERE stage = 'SENSING'
-- GROUP BY 1;
