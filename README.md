# CareSync-Pipeline
Quality-gated weekly ELT pipeline turning third-party clinic CSV exports into a validated Snowflake reporting layer, pre/post validation gates, skip-and-cascade failure isolation, Slack/email alerting, and a dbt star schema. Built twice: pandas + GitHub Actions, then Great Expectations + Airflow.
