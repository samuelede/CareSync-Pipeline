Checkpoints bind a suite to a batch of data and a set of actions (store
result, update Data Docs, trigger post-run hook). Create one checkpoint per
dataset, e.g. `patients_checkpoint.yml`, run via:

    great_expectations checkpoint run patients_checkpoint

The Airflow DAG (orchestration/airflow/dags/caresync_dag.py) calls these
via `GreatExpectationsOperator` per dataset, replacing the pandas
`rules_<dataset>.py` call used in Phase 1. Same gate, same cascade-skip
logic downstream, different validation engine.
