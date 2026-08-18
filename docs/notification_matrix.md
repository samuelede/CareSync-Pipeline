# Notification Matrix

| Event | Trigger | Channels | Key detail included |
|---|---|---|---|
| `SLA_MISSED` | expected file absent 1h past scheduled delivery | Slack + email | run_id, dataset, minutes late |
| `PRE_VALIDATION_FAILED` | a file fails any pre-validation check | Slack + email | run_id, dataset, failed checks, row count |
| `TASK_ERROR` | an unexpected pipeline/infra error (not a data-quality rejection) | Slack + email | run_id, task, stack trace summary |
| `POST_VALIDATION_FAILED` | PROD layer fails a business-rule check | Slack + email | run_id, failed rule, affected table |
| `RUN_SUCCESS` | full run completes, post-validation passes | Slack + email | run_id, per-dataset status, row counts loaded |

Every message carries `run_id` so it can be traced back to
`CARESYNC_WH.AUDIT.RUN_AUDIT` and, for pre-validation failures, to the
corresponding file under `quarantine/`.
