"""Tailscale staleness detector. One check per invocation; the counter lives in DynamoDB.

EventBridge Scheduler runs this every minute. It asks Tailscale when the app
host was last seen, and after THRESHOLD consecutive stale readings it scales the
ECS failover service up from zero and posts to Slack.

WHY THE COUNTER IS IN DYNAMODB. The original was a loop holding `misses` in
memory. Lambda invocations share nothing, so the count has to outlive the
process. One item, read and written once per minute.

THE RULE THAT MATTERS: a failed Tailscale API call is NOT a miss. If their API
is down or the key expired we cannot tell whether the device is healthy, and
that is not the same as knowing it is down — conflating them would let a
Tailscale outage fail over your own infrastructure. On any error this returns
without touching the counter.

Failback is deliberately manual. Nothing here ever scales back to zero.
"""

from __future__ import annotations

import json
import os

import boto3
import httpx
import pendulum
from botocore.exceptions import ClientError

REGION = "us-east-1"
SECRET_ID = os.environ.get("WISHLY_SECRETS_ID", "wishly/prod")
TABLE = os.environ["STATE_TABLE"]
DEVICE_ID = os.environ["TAILSCALE_DEVICE_ID"]
CLUSTER = os.environ["ECS_CLUSTER"]
SERVICE = os.environ["ECS_SERVICE"]

# Seconds since lastSeen beyond which a reading counts as stale. lastSeen is
# maintained by Tailscale's coordination server; nothing contracts it to update
# inside any particular window, so 60s is the conservative floor.
FRESH_WITHIN = int(os.environ.get("FRESH_WITHIN_SECONDS", "60"))
THRESHOLD = int(os.environ.get("THRESHOLD", "3"))

_ddb = boto3.client("dynamodb", region_name=REGION)
_ecs = boto3.client("ecs", region_name=REGION)
_secrets = boto3.client("secretsmanager", region_name=REGION)

# Module scope: a warm invocation reuses it rather than re-reading the secret
# every minute.
_config: dict[str, str] | None = None


def config() -> dict[str, str]:
    global _config
    if _config is None:
        raw = _secrets.get_secret_value(SecretId=SECRET_ID)["SecretString"]
        _config = json.loads(raw)
    return _config


def log(msg: str) -> None:
    print(f"{pendulum.now('UTC').to_iso8601_string()} {msg}", flush=True)


def age_seconds() -> float:
    """Seconds since the device was last seen. Raises on any API problem."""
    response = httpx.get(
        f"https://api.tailscale.com/api/v2/device/{DEVICE_ID}",
        headers={"Authorization": f"Bearer {config()['TAILSCALE_API_KEY']}"},
        timeout=15,
    )
    response.raise_for_status()
    last_seen = pendulum.parse(response.json()["lastSeen"])
    return float((pendulum.now("UTC") - last_seen).total_seconds())


def slack(text: str) -> None:
    """Post to Slack if configured. Never raises — the failover is the real signal."""
    url = config().get("SLACK_WEBHOOK_URL")
    if not url:
        log("no SLACK_WEBHOOK_URL, skipping alert")
        return
    try:
        httpx.post(url, json={"text": text}, timeout=10).raise_for_status()
    except httpx.HTTPError as exc:
        log(f"slack alert failed: {exc}")


def record(misses: int, age: float, state: str) -> None:
    _ddb.update_item(
        TableName=TABLE,
        Key={"id": {"S": "detector"}},
        UpdateExpression="SET misses = :m, last_age_seconds = :a, updated_at = :t, #s = :st",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={
            ":m": {"N": str(misses)},
            ":a": {"N": f"{age:.0f}"},
            ":t": {"S": pendulum.now("UTC").to_iso8601_string()},
            ":st": {"S": state},
        },
    )


def current() -> tuple[int, str]:
    item = _ddb.get_item(TableName=TABLE, Key={"id": {"S": "detector"}}).get("Item", {})
    return int(item.get("misses", {}).get("N", 0)), item.get("state", {}).get("S", "OK")


def claim_failover() -> bool:
    """Move OK -> DOWN atomically. False if someone already did.

    EventBridge Scheduler is at-least-once, so two invocations can overlap. A
    conditional write means only one of them ever calls update-service.
    """
    try:
        _ddb.update_item(
            TableName=TABLE,
            Key={"id": {"S": "detector"}},
            UpdateExpression="SET #s = :down",
            ConditionExpression="attribute_not_exists(#s) OR #s = :ok",
            ExpressionAttributeNames={"#s": "state"},
            ExpressionAttributeValues={":down": {"S": "DOWN"}, ":ok": {"S": "OK"}},
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def handler(event: object, context: object) -> dict[str, object]:
    try:
        age = age_seconds()
    except Exception as exc:  # noqa: BLE001 — any failure means "unknown", not "down"
        log(f"check failed: {exc}")
        return {"status": "unknown", "error": str(exc)}

    misses, state = current()

    if age < FRESH_WITHIN:
        if misses or state != "OK":
            log(f"ok ({age:.0f}s) — resetting")
        record(0, age, "OK")
        return {"status": "ok", "age": age}

    misses += 1
    log(f"stale {age:.0f}s ({misses}/{THRESHOLD})")
    record(misses, age, state)

    if misses < THRESHOLD:
        return {"status": "stale", "misses": misses}

    if not claim_failover():
        log("already DOWN, not failing over again")
        return {"status": "already_down"}

    log(f"DOWN after {THRESHOLD} stale checks — scaling {SERVICE} to 1")
    _ecs.update_service(cluster=CLUSTER, service=SERVICE, desiredCount=1)
    slack(f":red_circle: {DEVICE_ID} is DOWN (last seen {age:.0f}s ago) — scaled {SERVICE} to 1")
    return {"status": "failed_over", "age": age}
