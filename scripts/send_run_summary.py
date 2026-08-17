"""
Reads the local run audit trail for --run-id and sends the RUN_SUCCESS (or
run-failed) summary notification: per-dataset status, row counts, whether
post-validation passed. Called as the last step of both the GitHub Actions
workflow and run_local_pipeline.sh, always (even on prior-step failure).
"""
import argparse

from notifications.slack_notify import send_slack_alert
from notifications.email_notify import send_email_alert
from scripts.audit_log import read_run


def main(run_id: str):
    rows = read_run(run_id)
    if not rows:
        print(f"[send_run_summary] no audit rows found for run {run_id}")
        return

    per_dataset = {}
    post_validation_row = None
    for row in rows:
        if row["stage"] == "PRE_VALIDATION":
            per_dataset[row["dataset"]] = f"{row['status']} ({row['row_count']} rows)"
        if row["stage"] == "POST_VALIDATION":
            post_validation_row = row

    overall_ok = all("REJECTED" not in v and "FAILED" not in v for v in per_dataset.values())
    if post_validation_row and post_validation_row["status"] != "SUCCESS":
        overall_ok = False

    detail = {**per_dataset,
              "post_validation": post_validation_row["status"] if post_validation_row else "not run"}

    event = "RUN_SUCCESS" if overall_ok else "POST_VALIDATION_FAILED"
    send_slack_alert(event, run_id, detail)
    send_email_alert(event, run_id, detail)
    print(f"[send_run_summary] run {run_id}: {'SUCCESS' if overall_ok else 'ISSUES'}: {detail}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    main(args.run_id)
