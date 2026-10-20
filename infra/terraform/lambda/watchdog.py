"""Watchdog: ping Wishly every minute; push a notification once it's been down
for ALERT_AFTER_SECONDS, and again when it comes back.

EventBridge invokes this every minute. Each run writes one JSON line to
CloudWatch Logs. Down means anything but a 200 from /internal/ping: no answer,
a tunnel error from Cloudflare, a 503 (database or scheduler), or a 401 (the
ping key is wrong, which needs a human just as much).

State lives in one DynamoDB item, since invocations share nothing else:
  down_since  epoch seconds of the first failed check in this outage, or absent
  alerted     whether the "down" notification has gone out for this outage
It's only written when that changes, so a healthy minute is one read.

Standard library plus boto3, which the Lambda runtime includes.
"""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

import boto3

PING_URL = os.environ["PING_URL"]
PING_TOKEN = os.environ["PING_TOKEN"]
STATE_TABLE = os.environ["STATE_TABLE"]
ALERT_AFTER_SECONDS = int(os.environ.get("ALERT_AFTER_SECONDS", "300"))
NTFY_URL = os.environ.get("NTFY_URL", "")  # https://ntfy.sh/<topic>, or empty for none

# Name ourselves. Cloudflare's Browser Integrity Check rejects Python's default
# "Python-urllib/3.x" user agent with a 403 (error 1010) before the request
# ever reaches the API.
USER_AGENT = "wishly-watchdog/1.0"
STATE_KEY = {"id": {"S": "wishly"}}

dynamodb = boto3.client("dynamodb")


def handler(event, context):
    now = int(time.time())
    check = ping()
    state = load_state()
    down_since, alerted = state["down_since"], state["alerted"]

    if check["ok"]:
        if alerted:
            notify(
                "Wishly is back up",
                f"Down for {minutes(now - down_since)}. Last error: {state['last_error']}",
                priority="default",
                tags="white_check_mark",
            )
        if down_since is not None:
            save_state(None, False, None)
    else:
        if down_since is None:
            down_since = now
            save_state(down_since, False, check["error"])
        if not alerted and now - down_since >= ALERT_AFTER_SECONDS:
            notify(
                "Wishly is down",
                f"No healthy answer from {PING_URL} for {minutes(now - down_since)}.\n"
                f"Latest: {check['error']}",
                priority="high",
                tags="warning",
            )
            save_state(down_since, True, check["error"])

    record = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        **check,
        "down_for_s": None if check["ok"] or down_since is None else now - down_since,
    }
    print(json.dumps(record))
    return record


def ping():
    started = time.monotonic()
    request = urllib.request.Request(
        PING_URL, headers={"Authorization": f"Bearer {PING_TOKEN}", "User-Agent": USER_AGENT}
    )
    result = {"status": None, "error": None}
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            result["status"] = response.status
    except urllib.error.HTTPError as exc:  # it answered, with an error
        result["status"] = exc.code
        result["error"] = f"HTTP {exc.code}: {exc.read(200).decode(errors='replace')}"
    except Exception as exc:  # no answer: timeout, DNS
        result["error"] = repr(exc)
    result["ok"] = result["status"] == 200
    result["duration_ms"] = round((time.monotonic() - started) * 1000)
    return result


def load_state():
    item = dynamodb.get_item(TableName=STATE_TABLE, Key=STATE_KEY, ConsistentRead=True)
    item = item.get("Item", {})
    return {
        "down_since": int(item["down_since"]["N"]) if "down_since" in item else None,
        "alerted": item.get("alerted", {}).get("BOOL", False),
        "last_error": item.get("last_error", {}).get("S"),
    }


def save_state(down_since, alerted, last_error):
    item = {**STATE_KEY, "alerted": {"BOOL": alerted}}
    if down_since is not None:
        item["down_since"] = {"N": str(down_since)}
    if last_error:
        item["last_error"] = {"S": last_error[:500]}
    dynamodb.put_item(TableName=STATE_TABLE, Item=item)


def minutes(seconds):
    m = max(1, round(seconds / 60))
    return f"{m} minute{'' if m == 1 else 's'}"


def notify(title, body, *, priority, tags):
    if not NTFY_URL:
        return
    request = urllib.request.Request(
        NTFY_URL,
        data=body.encode(),
        method="POST",
        headers={"Title": title, "Priority": priority, "Tags": tags, "User-Agent": USER_AGENT},
    )
    try:
        urllib.request.urlopen(request, timeout=5).close()
    except Exception as exc:  # a broken notification must not crash the check
        print(json.dumps({"ntfy_error": repr(exc)}))
