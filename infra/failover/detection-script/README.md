# Device staleness detection

Polls the Tailscale API for a device's `lastSeen`, compares it to now, and exits
non-zero once the device has been stale for 3 consecutive checks. That non-zero
exit is the trigger a failover step keys off.

Dependencies are `httpx` and `pendulum`, managed by `uv` — so it runs through
`uv run`, never bare `python3`.

---

## Usage

```bash
uv sync                       # first time only
cp .env.example .env          # then add the real API key
uv run detect_stale_device.py
```

The script calls `load_dotenv()` on the `.env` sitting **next to the script**, so
it works from any working directory and needs no `--env-file` flag.

Real environment variables take precedence over the file. That's what keeps
deployment clean: systemd's `EnvironmentFile=` or podman's `--env-file` wins, and
a stray `.env` on the host can never silently override production config.

Tuning lives in constants at the top of `detect_stale_device.py`:
`DEVICE_ID`, `FRESH_WITHIN` (30 s), `THRESHOLD` (3), `INTERVAL` (30 s).
Only the API key comes from the environment, because only it is a secret.

---

## How it decides

```
poll every INTERVAL seconds
    │
    ├── lastSeen within FRESH_WITHIN  ──►  counter = 0        (healthy)
    ├── lastSeen older                ──►  counter += 1       (stale)
    │        └── counter == THRESHOLD ──►  exit 1             (down)
    └── API call raised               ──►  counter unchanged  (unknown)
```

The counter is **consecutive** — one healthy reading resets it, so three stale
checks spread across an hour trigger nothing.

**A failed API call never counts as a miss.** If Tailscale's API is down or the
key expired, we cannot tell whether the device is healthy, and that is not the
same as knowing it is down. Conflating them would let a Tailscale outage trigger
a failover of your infrastructure. Those log as `check failed:` and the loop
keeps going.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Interrupted, stopped cleanly |
| `1` | **Device is down** — threshold reached. Failover should act on this. |
| `2` | `TAILSCALE_API_KEY` not set |

---

## Tuning notes

**`FRESH_WITHIN = 30` is aggressive.** `lastSeen` is maintained by Tailscale's
coordination server, and while it stays current for a connected device, nothing
contracts it to update inside any particular window. Watch a known-healthy
device for a while before trusting 30 s — if you see stale readings on a device
that never went away, raise it to 60–90 s rather than raising the threshold.

**Detection latency** is `INTERVAL × THRESHOLD` plus however long the control
plane takes to stop refreshing `lastSeen` — about 90 seconds plus lag.

**Rate limits:** at a 30 s interval this is ~2,880 calls/day against one device
endpoint, comfortably inside Tailscale's limits. Don't poll below 15 s.

---

## Related

- `../../../docs/runbooks/aws-vpc-tailscale.md` — the tailnet and subnet router
  this watches over
- A variant using the **local** daemon (`tailscale status --json`, no API key)
  runs on the subnet router as `pve-watch.service`. Use that when the script
  runs on a machine already in the tailnet; use this one when it doesn't, or
  when you want a view independent of any single node.
