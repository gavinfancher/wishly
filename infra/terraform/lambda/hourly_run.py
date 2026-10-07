"""Hourly trigger: call the API's /internal/run, log the result, notify by ntfy.

EventBridge invokes this at minute 0 of every hour. Each run writes one JSON
line to CloudWatch Logs: when it ran, how long it took, and what the API said.

Notifications go to your phone when a run fails, or when it sent emails. Quiet
hours (nothing due, nothing wrong) send nothing, so the phone isn't pinged 24
times a day.

Standard library only, so there's nothing to install or package.
"""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime

RUN_URL = os.environ["RUN_URL"]
RUN_TOKEN = os.environ["RUN_TOKEN"]
NTFY_URL = os.environ.get("NTFY_URL", "")  # https://ntfy.sh/<topic>, or empty for none

# Name ourselves. Cloudflare's Browser Integrity Check rejects Python's default
# "Python-urllib/3.x" user agent with a 403 (error 1010) before the request
# ever reaches the API.
USER_AGENT = "wishly-hourly-run/1.0"


def handler(event, context):
    started = time.monotonic()
    record = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "url": RUN_URL}

    request = urllib.request.Request(
        RUN_URL,
        method="POST",
        headers={"Authorization": f"Bearer {RUN_TOKEN}", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=50) as response:
            record["status"] = response.status
            record.update(json.load(response))  # {"sent": n, "failed": m}
    except urllib.error.HTTPError as exc:  # the API answered with an error
        record["status"] = exc.code
        record["error"] = exc.reason
    except Exception as exc:  # it didn't answer: timeout, DNS, tunnel down
        record["status"] = None
        record["error"] = repr(exc)

    record["duration_ms"] = round((time.monotonic() - started) * 1000)
    record["ok"] = record["status"] == 200 and record.get("failed", 0) == 0
    print(json.dumps(record))
    notify(record)

    # Raising makes Lambda retry (see schedule.tf). That's safe: the API's
    # `sends` table means a retried run never emails anyone twice. Individual
    # email failures don't raise; the API already retries those next hour.
    if record["status"] != 200:
        raise RuntimeError(f"/internal/run failed: {record}")
    return record


def notify(record):
    if not NTFY_URL:
        return
    if record["ok"] and not record.get("sent"):
        return  # quiet hour

    if record["ok"]:
        sent = record["sent"]
        title = f"Wishly sent {sent} reminder{'' if sent == 1 else 's'}"
        priority, tags = "low", "white_check_mark"
    else:
        title = "Wishly hourly run failed"
        priority, tags = "high", "warning"

    request = urllib.request.Request(
        NTFY_URL,
        data=json.dumps(record, indent=1).encode(),
        method="POST",
        headers={"Title": title, "Priority": priority, "Tags": tags, "User-Agent": USER_AGENT},
    )
    try:
        urllib.request.urlopen(request, timeout=5).close()
    except Exception as exc:  # a broken notification must not fail the run
        print(json.dumps({"ntfy_error": repr(exc)}))
