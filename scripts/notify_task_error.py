"""
Fires a TASK_ERROR notification when a pipeline step crashes unexpectedly
(a Python exception, a non-zero exit from something that isn't a normal
data-quality REJECTED/FAILED outcome). Distinct from PRE_VALIDATION_FAILED
/POST_VALIDATION_FAILED, which fire when the pipeline works correctly and
finds bad data; TASK_ERROR fires when the pipeline itself is broken.

Usage (called from run_local_pipeline.sh's ERR trap, not run directly):
    python -m scripts.notify_task_error <run_id> <failed_command>
"""
import sys

from notifications.slack_notify import send_slack_alert
from notifications.email_notify import send_email_alert


def main(run_id: str, failed_command: str):
    detail = {"task": failed_command, "note": "pipeline step exited with an error, see terminal/CI log for the traceback"}
    send_slack_alert("TASK_ERROR", run_id, detail)
    send_email_alert("TASK_ERROR", run_id, detail)
    print(f"[notify_task_error] TASK_ERROR sent for run {run_id}, failed command: {failed_command}")


if __name__ == "__main__":
    run_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    failed_command = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    main(run_id, failed_command)
