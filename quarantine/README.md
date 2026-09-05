Rejected files land here as `quarantine/<run_id>/<dataset>.csv`, written by
`validation/pandas/pre_validate.py` (Phase 1) or the equivalent
GreatExpectationsOperator step (Phase 2). Nothing in this folder has ever
reached Snowflake. Each quarantined file has a matching row in
`NEXORA_RAW_WH.AUDIT.RUN_AUDIT` (status=REJECTED) recording which checks
failed, so the quarantine store and the audit table are always consistent.
