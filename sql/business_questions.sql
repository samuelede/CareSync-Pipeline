-- Answers to the reporting and data-quality business questions, run
-- against CARESYNC_WH.PROD once fct_appointments + dimensions exist.
-- Fill in each query against the actual mart column names once dbt has run.

-- Q1: Weekly appointment volume by clinic (organization)
-- SELECT o.organization_name, COUNT(*) AS appointments
-- FROM fct_appointments f JOIN dim_organization o USING (organization_key)
-- GROUP BY 1 ORDER BY 2 DESC;

-- Q2: Provider workload, appointments per provider, current run
-- SELECT p.provider_name, COUNT(*) AS appointments
-- FROM fct_appointments f JOIN dim_provider p USING (provider_key)
-- WHERE f._run_id = :run_id GROUP BY 1 ORDER BY 2 DESC;

-- Q3: Payer coverage mix
-- SELECT pay.payer_name, COUNT(*) AS appointments, SUM(f.coverage_amount) AS total_covered
-- FROM fct_appointments f JOIN dim_payer pay USING (payer_key)
-- GROUP BY 1 ORDER BY 2 DESC;

-- Q4: Data-quality question, runs with any REJECTED or SKIPPED dataset
-- SELECT run_id, dataset, status FROM CARESYNC_WH.AUDIT.RUN_AUDIT
-- WHERE status IN ('REJECTED', 'SKIPPED') ORDER BY recorded_at DESC;

-- Q5: SLA performance, percent of files on time over the last N runs
-- SELECT dataset, AVG(IFF(status = 'ON_TIME', 1, 0)) AS pct_on_time
-- FROM CARESYNC_WH.AUDIT.RUN_AUDIT WHERE stage = 'SENSING'
-- GROUP BY 1;
