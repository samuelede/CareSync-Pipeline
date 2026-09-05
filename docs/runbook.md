# Runbook

## A dataset was rejected, what do I do?
1. Check the Slack/email alert for `run_id` and `dataset`.
2. Query `NEXORA_RAW_WH.AUDIT.RUN_AUDIT` for that run/dataset row.
   `failed_checks` lists exactly which rule(s) failed.
3. Inspect the file at `quarantine/<run_id>/<dataset>.csv`.
4. If it's a genuine third-party data problem, contact the aggregation
   agent; do not manually force-load a quarantined file.
5. Dependent datasets that cascade-skipped will backfill automatically on
   the next successful run of the rejected dataset. No manual replay
   needed unless the SLA for a make-up delivery is also missed.

## A task errored (not a rejection)
This is a `TASK_ERROR`, not a skip. Something in the pipeline itself
broke (connection, credential, infra). Check the GitHub Actions run log
(Phase 1) or the Airflow task log (Phase 2) for the failing task.

## Post-validation failed
The input files were all clean but the PROD layer still violates a
business rule (e.g. orphan keys, PHI leak, count mismatch). Do not treat
the run as trusted. Investigate the dbt models before consuming
`fct_appointments` for reporting.
