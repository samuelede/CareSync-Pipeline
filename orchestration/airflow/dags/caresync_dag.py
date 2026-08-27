"""
CareSync production DAG (Phase 2).

Same stages and same skip-not-fail / cascade-skip semantics as the
GitHub Actions workflow, re-expressed with real dependency management:

    sense_files (FileSensor, 1h SLA via `timeout` + `sla`)
        |
    [pre_validate_<dataset>]  <- one GreatExpectationsOperator per dataset,
        |                        each wired with trigger_rule so a skip
        |                        propagates only to its dependents
    load_<dataset>_to_snowflake  (SnowflakeOperator / PythonOperator, skipped
        |                         via AirflowSkipException if pre-validation
        |                         rejected that dataset)
    dbt_run  (BashOperator or Cosmos, waits on all load tasks)
        |
    post_validate  (GreatExpectationsOperator against NEXORA_PROD_WH.PROD)
        |
    notify_run_summary  (trigger_rule=ALL_DONE, always runs even on failure,
                          so a run is never silent)

Per-task failures call notify_task_error via on_failure_callback; SLA
misses use the sensor's own `sla` parameter + an sla_miss_callback.

Fill in each PythonOperator/GreatExpectationsOperator with the same
functions already built in Phase 1 (sensing/, validation/, loaders/,
notifications/), only the orchestration mechanism changes, not the logic.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule

from config.settings import DATASET_MANIFEST

default_args = {
    "owner": "caresync",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    # "on_failure_callback": notify_task_error,  # see notifications/
}

with DAG(
    dag_id="caresync_weekly_pipeline",
    default_args=default_args,
    schedule_interval="0 6 * * 1",   # 06:00 UTC Monday, matches SCHEDULED_DELIVERY_TIME_UTC
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["caresync", "production"],
) as dag:

    def sense_files(**context):
        raise NotImplementedError("Call sensing/drive_sensor.py logic; sla param covers 1h SLA.")

    def pre_validate(dataset: str, **context):
        raise NotImplementedError(
            f"Run GE checkpoint for {dataset}; raise AirflowSkipException on rejection "
            "and push status to XCom for downstream cascade check."
        )

    def load_to_snowflake(dataset: str, **context):
        raise NotImplementedError(
            f"Check upstream XCom status for {dataset} and its deps in DATASET_MANIFEST; "
            "skip via AirflowSkipException if any dependency was rejected/skipped."
        )

    def run_dbt(**context):
        raise NotImplementedError("BashOperator or PythonOperator invoking `dbt run`.")

    def post_validate(**context):
        raise NotImplementedError("Run GE checkpoint against NEXORA_PROD_WH.PROD.")

    def notify_run_summary(**context):
        raise NotImplementedError("Send Slack + email success/failure summary, always runs.")

    sense = PythonOperator(task_id="sense_files", python_callable=sense_files)

    pre_validate_tasks = {}
    load_tasks = {}
    for dataset in DATASET_MANIFEST:
        pre_validate_tasks[dataset] = PythonOperator(
            task_id=f"pre_validate_{dataset}",
            python_callable=pre_validate,
            op_kwargs={"dataset": dataset},
        )
        load_tasks[dataset] = PythonOperator(
            task_id=f"load_{dataset}",
            python_callable=load_to_snowflake,
            op_kwargs={"dataset": dataset},
        )
        sense >> pre_validate_tasks[dataset] >> load_tasks[dataset]

    dbt_task = PythonOperator(task_id="dbt_run", python_callable=run_dbt)
    for dataset in DATASET_MANIFEST:
        load_tasks[dataset] >> dbt_task

    post_validate_task = PythonOperator(task_id="post_validate", python_callable=post_validate)
    dbt_task >> post_validate_task

    summary_task = PythonOperator(
        task_id="notify_run_summary",
        python_callable=notify_run_summary,
        trigger_rule=TriggerRule.ALL_DONE,
    )
    post_validate_task >> summary_task
