#!/usr/bin/env python3
"""Watch a Tailscale device; exit 1 once it goes stale THRESHOLD checks in a row.

    uv run detect_stale_device.py

Exit 1 is the failover trigger: whatever supervises this process (a systemd unit
with `OnFailure=`, or a wrapper that starts the standby EC2 instance) keys off it.
That is why the loop exits rather than alerting and continuing — an alert nobody
acts on is not a failover.

All configuration comes from the environment. Never hardcode the API key.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
import pendulum
from dotenv import load_dotenv

# Loads the .env sitting next to this script, so it works from any working
# directory. Real environment variables take precedence over the file: that is
# what keeps deployment clean — systemd's EnvironmentFile= or podman's --env-file
# wins, and a stray .env on the host can never silently override production.
load_dotenv(Path(__file__).with_name(".env"))

API_KEY = os.environ.get("TAILSCALE_API_KEY")
DEVICE_ID = os.environ.get("TAILSCALE_DEVICE_ID")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


def _int_env(name: str, default: int) -> int:
    """Read a positive integer tunable, falling back to ``default`` if unusable."""
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return value if value > 0 else default


# Seconds since `lastSeen` beyond which a reading counts as stale. `lastSeen` is
# maintained by Tailscale's coordination server, and while it stays current for a
# connected device, nothing contracts it to update inside any particular window.
# 60s is the conservative floor; watch a known-healthy device before lowering it.
FRESH_WITHIN = _int_env("FRESH_WITHIN_SECONDS", 60)
# Consecutive stale readings before declaring the device down.
THRESHOLD = _int_env("THRESHOLD", 3)
# Seconds between polls. At 60s this is ~1,440 calls/day against one device
# endpoint, comfortably inside Tailscale's limits. Do not poll below 15s.
INTERVAL = _int_env("INTERVAL_SECONDS", 60)

URL = f"https://api.tailscale.com/api/v2/device/{DEVICE_ID}"


def log(msg: str) -> None:
    stamp = pendulum.now("UTC").format("YYYY-MM-DDTHH:mm:ss[Z]")
    print(f"{stamp} {msg}", flush=True)


def slack_alert(text: str) -> None:
    """Post to Slack if a webhook is configured. Never raises.

    A failed alert must not take down the watchdog: the exit code is the real
    failover signal, and Slack is only how a human finds out.
    """
    if not SLACK_WEBHOOK_URL:
        log("no SLACK_WEBHOOK_URL, skipping alert")
        return
    try:
        httpx.post(SLACK_WEBHOOK_URL, json={"text": text}, timeout=10).raise_for_status()
    except httpx.HTTPError as exc:
        log(f"slack alert failed: {exc}")


def age_seconds() -> float:
    """Seconds since the device was last seen. Raises on any API problem."""
    response = httpx.get(URL, headers={"Authorization": f"Bearer {API_KEY}"}, timeout=15)
    response.raise_for_status()
    last_seen = pendulum.parse(response.json()["lastSeen"])
    return float((pendulum.now("UTC") - last_seen).total_seconds())


def main() -> int:
    if not API_KEY:
        log("TAILSCALE_API_KEY is not set")
        return 2
    if not DEVICE_ID:
        log("TAILSCALE_DEVICE_ID is not set")
        return 2

    log(f"watching {DEVICE_ID}: stale after {FRESH_WITHIN}s, down after {THRESHOLD} in a row")
    misses = 0

    while True:
        try:
            age = age_seconds()
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            # A failed API call is NOT a miss. If Tailscale's API is down or the
            # key expired we cannot tell whether the device is healthy, and that
            # is not the same as knowing it is down. Conflating them would let a
            # Tailscale outage trigger a failover of your own infrastructure.
            log(f"check failed: {exc}")
        else:
            if age < FRESH_WITHIN:
                misses = 0
                log(f"ok ({age:.0f}s)")
            else:
                misses += 1
                log(f"stale {age:.0f}s ({misses}/{THRESHOLD})")
                if misses >= THRESHOLD:
                    log(f"DOWN after {THRESHOLD} stale checks")
                    slack_alert(f"🔴 {DEVICE_ID} is DOWN — last seen {age:.0f}s ago")
                    return 1

        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("interrupted")
        sys.exit(0)
