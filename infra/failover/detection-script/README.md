# Device staleness detection

Polls the Tailscale API for a device's `lastSeen`, compares it to now, and **exits
non-zero once the device has been stale for 3 consecutive checks**. That non-zero
exit is the trigger a failover step keys off — see
[../README.md](../README.md) for where it fits.

Dependencies are `httpx` and `pendulum`, managed by `uv` — so it runs through
`uv run`, never bare `python3`.

---

## Usage

```bash
uv sync                       # first time only
cp .env.example .env          # then add the API key and device id
uv run detect_stale_device.py
```

The script calls `load_dotenv()` on the `.env` sitting **next to the script**, so
it works from any working directory and needs no `--env-file` flag.

Real environment variables take precedence over the file. That's what keeps
deployment clean: systemd's `EnvironmentFile=` or podman's `--env-file` wins, and
a stray `.env` on the host can never silently override production config.

---

## Configuration

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `TAILSCALE_API_KEY` | yes | — | Access token with `device:read` |
| `TAILSCALE_DEVICE_ID` | yes | — | The node to watch |
| `SLACK_WEBHOOK_URL` | no | — | Alert destination; absence only skips the alert |
| `FRESH_WITHIN_SECONDS` | no | `60` | Age beyond which a reading is stale |
| `THRESHOLD` | no | `3` | Consecutive stale readings before declaring down |
| `INTERVAL_SECONDS` | no | `60` | Seconds between polls |

Only the API key and the webhook are secrets; the rest are tuning.

---

## How it decides

```
poll every INTERVAL seconds
    │
    ├── lastSeen within FRESH_WITHIN  ──►  counter = 0        (healthy)
    ├── lastSeen older                ──►  counter += 1       (stale)
    │        └── counter == THRESHOLD ──►  alert, exit 1      (down)
    └── API call raised               ──►  counter unchanged  (unknown)
```

The counter is **consecutive** — one healthy reading resets it, so three stale
checks spread across an hour trigger nothing.

**A failed API call never counts as a miss.** If Tailscale's API is down or the
key expired, we cannot tell whether the device is healthy, and that is not the
same as knowing it is down. Conflating them would let a Tailscale outage trigger
a failover of your infrastructure. Those log as `check failed:` and the loop
keeps going.

**A failed Slack post never stops the watchdog** either. The exit code is the real
signal; Slack is only how a human finds out.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Interrupted (Ctrl-C), stopped cleanly |
| `1` | **Device is down** — threshold reached. Failover should act on this. |
| `2` | `TAILSCALE_API_KEY` or `TAILSCALE_DEVICE_ID` not set |

---

## Tuning notes

**`FRESH_WITHIN_SECONDS` defaults to 60, deliberately.** `lastSeen` is maintained
by Tailscale's coordination server, and while it stays current for a connected
device, nothing contracts it to update inside any particular window. An earlier
30s setting was aggressive enough to risk false positives. Watch a known-healthy
device for a while before lowering it; if you see stale readings on a device that
never went away, raise it to 90s rather than raising the threshold.

**Detection latency** is `INTERVAL × THRESHOLD` plus however long the control
plane takes to stop refreshing `lastSeen` — about three minutes at the defaults,
plus lag. Budget for that on top of EC2 boot time when reasoning about how much of
an hour a failover costs (see DEPLOYMENT-PLAN T7).

**Rate limits:** at a 60s interval this is ~1,440 calls/day against one device
endpoint, comfortably inside Tailscale's limits. Don't poll below 15s.

---

## Related

- `../../../docs/runbooks/aws-vpc-tailscale.md` — the tailnet and subnet router
  this watches over
- A variant using the **local** daemon (`tailscale status --json`, no API key)
  can run on the subnet router itself. Use that when the script runs on a machine
  already in the tailnet; use this one when it doesn't, or when you want a view
  independent of any single node.
