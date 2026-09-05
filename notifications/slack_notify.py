"""
Sends CareSync alerts to Slack via slack_sdk (Bot Token + a channel the app
has been invited to).

Setup:
    1. Create a Slack app at api.slack.com/apps -> "From scratch"
    2. Add Bot Token Scope: chat:write
    3. Install app to workspace, copy the Bot User OAuth Token -> SLACK_BOT_TOKEN
    4. Invite the bot to the target channel, copy the channel ID -> SLACK_CHANNEL_ID

Usage:
    from notifications.slack_notify import send_slack_alert
    send_slack_alert(event="SLA_MISSED", run_id="2026-08-10", detail={...})

Event types (the full notification matrix from the spec):
    SLA_MISSED, PRE_VALIDATION_FAILED, TASK_ERROR, POST_VALIDATION_FAILED, RUN_SUCCESS

Every message must include the run_id so any alert is traceable back to a
row in the run audit table.
"""
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from config.settings import SLACK_BOT_TOKEN, SLACK_CHANNEL_ID

EVENT_EMOJI = {
    "SLA_MISSED": ":alarm_clock:",
    "PRE_VALIDATION_FAILED": ":x:",
    "TASK_ERROR": ":boom:",
    "POST_VALIDATION_FAILED": ":warning:",
    "RUN_SUCCESS": ":white_check_mark:",
}


def format_message(event: str, run_id: str, detail: dict) -> str:
    header = [f"{EVENT_EMOJI.get(event, ':bell:')} *CareSync: {event}*", f"Run ID: `{run_id}`"]
    lines = header + [f"*{k}:* {v}" for k, v in detail.items()]
    return "\n".join(lines)


def send_slack_alert(event: str, run_id: str, detail: dict):
    message = format_message(event, run_id, detail)
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL_ID:
        print(f"[slack_notify] SLACK_BOT_TOKEN/SLACK_CHANNEL_ID not configured. "
              f"Would have sent:\n{message}")
        return
    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        client.chat_postMessage(channel=SLACK_CHANNEL_ID, text=message)
    except SlackApiError as e:
        print(f"[slack_notify] failed to send: {e.response['error']}")
    except Exception as e:
        print(f"[slack_notify] failed to send: {e}")
