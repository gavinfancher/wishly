#!/usr/bin/env python3
"""Watch a Tailscale device; exit 1 once it goes stale 3 checks in a row.

    uv run detect_stale_device.py

The API key comes from the environment. Never hardcode it.
"""

import os
import sys
import time
from pathlib import Path

import httpx
import pendulum
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

API_KEY = os.environ.get("TAILSCALE_API_KEY")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


DEVICE_ID = "nRHb3Tj5Ax11CNTRL" # the device ID of my proxmox node that the compute and db node are running on
URL = f"https://api.tailscale.com/api/v2/device/{DEVICE_ID}"

FRESH_WITHIN = 30
THRESHOLD = 3
INTERVAL = 60


def log(msg: str) -> None:
    stamp = pendulum.now("UTC").format("YYYY-MM-DDTHH:mm:ss[Z]")
    print(f"{stamp} {msg}", flush=True)


def slack_alert(text: str) -> None:
    response = httpx.post(
        SLACK_WEBHOOK_URL,
        json={"text": text},
        timeout=10
    )
    response.raise_for_status()


def age_seconds() -> float:
    """Seconds since the device was last seen. Raises on any API problem."""
    response = httpx.get(
        URL,
        headers = {
            "Authorization": f"Bearer {API_KEY}"},
            timeout=15
    )
    response.raise_for_status()
    last_seen = pendulum.parse(response.json()["lastSeen"])
    age_in_seconds = (pendulum.now("UTC") - last_seen).total_seconds()
    return age_in_seconds


def main() -> int:
    misses = 0

    while True:
        age = age_seconds()
        
        if age < FRESH_WITHIN:
            misses = 0
            log(f"ok ({age:.0f}s)")
        else:
            misses += 1
            log(f"stale {age:.0f}s ({misses}/{THRESHOLD})")
            if misses >= THRESHOLD:
                log(f"DOWN after {THRESHOLD} stale checks")
                slack_alert(f"🔴 PVE-Root is DOWN — last seen {age:.0f}s ago ")

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()