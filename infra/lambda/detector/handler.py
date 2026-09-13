"""Liveness detector. One probe per invocation; the counter lives in DynamoDB.

EventBridge runs this every minute. It asks the Wishly API whether it is serving
and which deployment answered, and after THRESHOLD consecutive misses it scales
the ECS failover service up from zero and posts to Slack.

WHY NOT TAILSCALE ANY MORE. This used to ask Tailscale when the VM's daemon last
checked in, which answers "is the host powered on" — not "is Wishly working".
Tailscale stays green while the API crashloops, the tunnel token expires, or
cloudflared dies, and all three are outages. Probing GET /internal/liveness
measures the path users actually take: Cloudflare's edge, the tunnel, and the
API process. It is also one fewer third-party API and one fewer credential.

WHY THE RESPONSE NAMES A HOST. api.wishly.dev is served by whichever cloudflared
is connected, so after a failover the ECS task answers and the probe succeeds
while the VM is still dead. Without `host` in the body, the very next minute
would look like a recovery.

WHY THE COUNTER IS IN DYNAMODB. The original was a loop holding `misses` in
memory. Lambda invocations share nothing, so the count has to outlive the
process. One item, read and written once per minute.

THE RULE THAT MATTERS, UNCHANGED: a failed check is NOT a miss. It is only a
miss when we have positive evidence that nothing is serving — Cloudflare
answering 502/503/530, which means its edge is healthy and found no tunnel
origin. If we cannot reach Cloudflare at all, or the token is wrong, we do not
know anything, and failing over on "do not know" would let a problem on this
side of the connection spend money to fix nothing.

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
API_URL = os.environ["WISHLY_API_URL"].rstrip("/")
CLUSTER = os.environ["ECS_CLUSTER"]
SERVICE = os.environ["ECS_SERVICE"]

# Must match TRIGGER_HEADER in wishly.api.routes.internal.
TRIGGER_HEADER = "X-Wishly-Trigger"

# Comfortably longer than a healthy round trip to Cloudflare's edge and back
# through the tunnel, and comfortably shorter than the one-minute schedule.
PROBE_TIMEOUT = float(os.environ.get("PROBE_TIMEOUT_SECONDS", "10"))
THRESHOLD = int(os.environ.get("THRESHOLD", "3"))

# Cloudflare's "the edge is fine, the origin is not" family. 530 is its
# tunnel-specific one (no cloudflared connected); 502/503/504 cover an origin
# that accepted the connection and then failed. These are positive evidence of
# an outage, which is what separates them from a timeout.
NO_ORIGIN_STATUSES = frozenset({502, 503, 504, 520, 521, 522, 523, 524, 530})

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


class Unknown(Exception):
    """We could not determine anything. Never counts as a miss."""


def probe() -> str:
    """Which deployment is serving: ``"vm"``, ``"ecs"``, or ``"none"``.

    Raises :class:`Unknown` for everything that does not answer that question,
    so the caller can leave the counter alone. The split is the whole point of
    this function:

    * A **5xx from Cloudflare** means its edge is up and no tunnel origin is
      connected. That is an outage, and it returns ``"none"``.
    * A **connect error, DNS failure, or timeout** means we could not reach
      Cloudflare. That says nothing about the VM, and failing over would not help
      if Cloudflare itself were the problem.
    * A **403** means the trigger token is wrong. The app may be perfectly
      healthy; scaling ECS up would not fix a bad secret, and the fix is a
      deploy, not a failover.
    """
    try:
        token = config()["TRIGGER_TOKEN"]
    except Exception as exc:  # noqa: BLE001 — no secret means no verdict
        raise Unknown(f"could not read TRIGGER_TOKEN: {exc}") from exc

    try:
        response = httpx.get(
            f"{API_URL}/internal/liveness",
            headers={TRIGGER_HEADER: token},
            timeout=PROBE_TIMEOUT,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise Unknown(f"could not reach {API_URL}: {exc}") from exc

    if response.status_code in NO_ORIGIN_STATUSES:
        return "none"
    if response.status_code == 403:
        raise Unknown("403 from the API — trigger token mismatch, not an outage")
    if response.status_code != 200:
        raise Unknown(f"unexpected status {response.status_code}")

    try:
        host = str(response.json()["host"])
    except Exception as exc:  # noqa: BLE001 — a body we cannot read is not a verdict
        raise Unknown(f"unreadable liveness body: {exc}") from exc

    if host not in ("vm", "ecs"):
        raise Unknown(f"unrecognised host {host!r}")
    return host


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


def record(misses: int, serving: str, state: str) -> None:
    """Persist the counter and what the last probe saw.

    ``last_seen_host`` replaces the old ``last_age_seconds``: there is no age to
    report now, and "who answered the last probe" is the thing you actually want
    when reading this item during an incident.
    """
    _ddb.update_item(
        TableName=TABLE,
        Key={"id": {"S": "detector"}},
        UpdateExpression="SET misses = :m, last_seen_host = :h, updated_at = :t, #s = :st",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={
            ":m": {"N": str(misses)},
            ":h": {"S": serving},
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
        serving = probe()
    except Unknown as exc:
        # Not a miss. See the module docstring: we only count what we can prove.
        log(f"probe inconclusive: {exc}")
        return {"status": "unknown", "error": str(exc)}

    misses, state = current()

    if serving == "vm":
        if misses or state != "OK":
            log("vm is serving again — resetting")
        record(0, serving, "OK")
        return {"status": "ok", "host": serving}

    if serving == "ecs":
        # Already failed over. The VM has not come back — the standby is simply
        # answering for it — so neither count this nor clear the counter, and
        # never scale a service that is already up. Failback stays manual.
        log("ecs is serving — already failed over, leaving state alone")
        return {"status": "already_failed_over", "host": serving}

    # serving == "none": Cloudflare's edge answered and found no tunnel origin.
    misses += 1
    log(f"no origin serving ({misses}/{THRESHOLD})")
    record(misses, serving, state)

    if misses < THRESHOLD:
        return {"status": "missing", "misses": misses}

    if not claim_failover():
        log("already DOWN, not failing over again")
        return {"status": "already_down"}

    log(f"DOWN after {THRESHOLD} failed probes — scaling {SERVICE} to 1")
    _ecs.update_service(cluster=CLUSTER, service=SERVICE, desiredCount=1)
    slack(
        f":red_circle: {API_URL} has no origin serving after {THRESHOLD} probes "
        f"— scaled {SERVICE} to 1"
    )
    return {"status": "failed_over"}
