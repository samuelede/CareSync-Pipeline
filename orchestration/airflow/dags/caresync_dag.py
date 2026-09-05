"""
CareSync production DAG (Phase 2). Same stages and same skip-not-fail /
cascade-skip semantics as the GitHub Actions workflow, wired to Airflow's
real dependency management instead of a linear bash script.

Every task callable below is a thin wrapper around a module already built
and proven in Phase 1: sensing, validation.pandas.pre_validate (or
validation.great_expectations, selected the same way, via
config.settings.VALIDATION_ENGINE), loaders.snowflake_loader, dbt, and
validation.pandas.post_validate. No business logic lives in this file,
matching the project's core lesson: only the orchestration mechanism
changes between phases, not the rules being enforced.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.exceptions import AirflowSkipException

from config.settings import DATASET_MANIFEST

default_args = {
    "owner": "caresync",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _sense_files(**context):
    from sensing.sftp_sensor import main as sftp_main
    run_id = context["ds"]
    results = sftp_main(run_id)
    context["ti"].xcom_push(key="sensing_results", value=results)


def _pre_validate(**context):
    from validation.pandas.pre_validate import main as pre_validate_main
    run_id = context["ds"]
    status = pre_validate_main(run_id)
    context["ti"].xcom_push(key="validation_status", value=status)


def _load_dataset(dataset: str, **context):
    """Skips (not fails) if pre_validate marked this dataset REJECTED or
    SKIPPED, mirroring run_local_pipeline.sh's [skip] log line exactly."""
    from loaders.snowflake_loader import load_dataset
    status = context["ti"].xcom_pull(key="validation_status", task_ids="pre_validate")
    run_id = context["ds"]
    if not status or status.get(dataset) != "VALID":
        raise AirflowSkipException(f"{dataset} is {status.get(dataset) if status else 'unknown'}, not loading")
    load_dataset(dataset, run_id)


def _run_dbt(**context):
    import subprocess
    result = subprocess.run(
        ["dbt", "run", "--target", "dev_keypair"],
        cwd="dbt_caresync", capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        raise RuntimeError(f"dbt run failed with exit code {result.returncode}")


def _post_validate(**context):
    from validation.pandas.post_validate import main as post_validate_main
    run_id = context["ds"]
    passed = post_validate_main(run_id)
    if not passed:
        raise RuntimeError("post-validation failed business-rule checks, see POST_VALIDATION_FAILED alert")


def _send_run_summary(**context):
    from scripts.send_run_summary import main as summary_main
    run_id = context["ds"]
    summary_main(run_id)


with DAG(
    dag_id="caresync_weekly_pipeline",
    default_args=default_args,
    schedule_interval="0 6 * * 1",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["caresync", "production"],
) as dag:

    sense = PythonOperator(task_id="sense_files", python_callable=_sense_files)
    pre_validate = PythonOperator(task_id="pre_validate", python_callable=_pre_validate)
    sense >> pre_validate

    load_tasks = {}
    for dataset in DATASET_MANIFEST:
        load_tasks[dataset] = PythonOperator(
            task_id=f"load_{dataset}",
            python_callable=_load_dataset,
            op_kwargs={"dataset": dataset},
        )
        pre_validate >> load_tasks[dataset]

    dbt_task = PythonOperator(
        task_id="dbt_run",
        python_callable=_run_dbt,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )
    for dataset in DATASET_MANIFEST:
        load_tasks[dataset] >> dbt_task

    post_validate_task = PythonOperator(task_id="post_validate", python_callable=_post_validate)
    dbt_task >> post_validate_task

    summary_task = PythonOperator(
        task_id="notify_run_summary",
        python_callable=_send_run_summary,
        trigger_rule=TriggerRule.ALL_DONE,
    )
    post_validate_task >> summary_task
